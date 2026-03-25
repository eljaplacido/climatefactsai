"""
Climate Data API -asiakkaat

Asiakkaat Open-Meteo (ilmastoriski), NOAA ja NASA POWER -API:ille.
"""

import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

import requests
from structlog.stdlib import BoundLogger


class OpenMeteoClient:
    """
    Open-Meteo API -asiakas (ilmainen, ei vaadi API-avainta)

    Hakee sää- ja ilmastodataa, mukaan lukien:
    - Lämpötilat (nykyiset ja historialliset)
    - Sademäärät
    - Äärisääilmiöt
    - Ilmastotrendit

    Dokumentaatio: https://open-meteo.com/en/docs
    """

    def __init__(
        self,
        api_url: str = "https://api.open-meteo.com/v1",
        logger: Optional[BoundLogger] = None
    ):
        """
        Alusta Open-Meteo -asiakas

        Args:
            api_url: API:n base URL
            logger: Logger
        """
        self.api_url = api_url.rstrip("/")
        self.logger = logger
        self.session = requests.Session()

        if self.logger:
            self.logger.info("Open-Meteo client initialized (no API key required)")

    def get_climate_data(
        self,
        latitude: float,
        longitude: float,
        days_back: int = 30
    ) -> Optional[Dict[str, Any]]:
        """
        Hae ilmastodataa sijainnille (nykyinen + historiallinen)

        Args:
            latitude: Leveyspiiri
            longitude: Pituuspiiri
            days_back: Montako päivää historiallista dataa

        Returns:
            Dictionary ilmastodataa tai None
        """
        endpoint = f"{self.api_url}/forecast"

        # Laske päivämääräväli
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        try:
            start_time = time.time()

            # Hae nykyiset ja historialliset tiedot
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max",
                "timezone": "auto",
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d")
            }

            response = self.session.get(
                endpoint,
                params=params,
                timeout=30
            )

            duration_ms = (time.time() - start_time) * 1000

            if self.logger:
                self.logger.info(
                    "Open-Meteo API call",
                    endpoint=endpoint,
                    status_code=response.status_code,
                    duration_ms=duration_ms
                )

            response.raise_for_status()
            data = response.json()

            # Analysoi data ja laske riskit
            daily = data.get("daily", {})
            temps_max = daily.get("temperature_2m_max", [])
            temps_min = daily.get("temperature_2m_min", [])
            precipitation = daily.get("precipitation_sum", [])
            windspeed = daily.get("windspeed_10m_max", [])

            # Laske tilastot
            if temps_max and temps_min:
                avg_temp = sum(temps_max + temps_min) / (len(temps_max) + len(temps_min))
                max_temp = max(temps_max) if temps_max else None
                total_precip = sum(precipitation) if precipitation else 0
                max_wind = max(windspeed) if windspeed else None

                # Arvioi ilmastoriskit yksinkertaisella logiikalla
                risk_score = self._calculate_risk_score(
                    avg_temp, max_temp, total_precip, max_wind
                )

                hazard_type = self._determine_hazard_type(
                    max_temp, total_precip, max_wind
                )

                return {
                    "source": "Open-Meteo",
                    "latitude": latitude,
                    "longitude": longitude,
                    "hazardType": hazard_type,
                    "riskScore": risk_score,
                    "confidence": 0.85,  # Open-Meteo on luotettava lähde
                    "data": {
                        "avgTemperature": round(avg_temp, 1),
                        "maxTemperature": round(max_temp, 1) if max_temp else None,
                        "totalPrecipitation": round(total_precip, 1),
                        "maxWindSpeed": round(max_wind, 1) if max_wind else None,
                        "daysAnalyzed": days_back
                    },
                    "timestamp": datetime.now().isoformat()
                }

            return None

        except requests.RequestException as e:
            if self.logger:
                self.logger.error(
                    "Open-Meteo API error",
                    error=str(e),
                    latitude=latitude,
                    longitude=longitude
                )
            return None

    def _calculate_risk_score(
        self,
        avg_temp: float,
        max_temp: Optional[float],
        total_precip: float,
        max_wind: Optional[float]
    ) -> int:
        """
        Laske yksinkertainen ilmastoriski-pisteet 0-100

        Args:
            avg_temp: Keskimääräinen lämpötila
            max_temp: Maksimilämpötila
            total_precip: Kokonaissademäärä
            max_wind: Maksimituulennopeus

        Returns:
            Risk score 0-100
        """
        risk = 0

        # Lämpötila-riski (korkeampi = korkeampi riski)
        if max_temp:
            if max_temp > 35:
                risk += 30  # Äärimmäinen kuumuus
            elif max_temp > 30:
                risk += 20
            elif max_temp > 25:
                risk += 10

            if max_temp < -20:
                risk += 20  # Äärimmäinen kylmyys
            elif max_temp < -10:
                risk += 10

        # Sade-riski
        if total_precip > 200:  # mm per kausi
            risk += 25  # Tulvariski
        elif total_precip > 100:
            risk += 15
        elif total_precip < 10:
            risk += 15  # Kuivuusriski

        # Tuuli-riski
        if max_wind:
            if max_wind > 25:  # m/s
                risk += 25  # Myrskyriski
            elif max_wind > 20:
                risk += 15

        return min(100, risk)  # Cap at 100

    def _determine_hazard_type(
        self,
        max_temp: Optional[float],
        total_precip: float,
        max_wind: Optional[float]
    ) -> str:
        """
        Määritä pääasiallinen ilmastovaara

        Returns:
            hazard type: "heat", "flood", "drought", "storm", "normal"
        """
        if max_temp and max_temp > 30:
            return "heat"
        elif total_precip > 150:
            return "flood"
        elif total_precip < 10:
            return "drought"
        elif max_wind and max_wind > 20:
            return "storm"
        else:
            return "normal"


class NOAAClient:
    """
    NOAA (National Oceanic and Atmospheric Administration) API -asiakas

    Hakee historiallista ilmastodataa GHCND (Global Historical Climatology Network Daily)
    -datasetistä.
    """

    def __init__(
        self,
        api_token: Optional[str],
        api_url: str = "https://www.ncdc.noaa.gov/cdo-web/api/v2",
        logger: Optional[BoundLogger] = None
    ):
        """
        Alusta NOAA-asiakas

        Args:
            api_token: API-token (required for NOAA CDO)
            api_url: API:n base URL
            logger: Logger
        """
        self.api_token = api_token
        self.api_url = api_url.rstrip("/")
        self.logger = logger

        self.session = requests.Session()
        if api_token:
            self.session.headers.update({
                "token": api_token
            })

    def get_climate_data(
        self,
        location: str,
        data_type: str = "temperature",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Hae ilmastodataa NOAA:lta

        Args:
            location: Paikka (kaupungin nimi)
            data_type: Datan tyyppi (temperature, precipitation, etc.)
            start_date: Alkupäivä (YYYY-MM-DD)
            end_date: Loppupäivä (YYYY-MM-DD)
            latitude: Leveyspiiri (optional, auttaa löytämään lähimmän aseman)
            longitude: Pituuspiiri (optional)

        Returns:
            Dictionary dataa tai None
        """
        if not self.api_token:
            if self.logger:
                self.logger.warning("NOAA API token not configured")
            return None

        # Määritä datatyypit
        datatypes_map = {
            "temperature": ["TMAX", "TMIN", "TAVG"],  # Max, Min, Average temp
            "precipitation": ["PRCP"],  # Precipitation
            "all": ["TMAX", "TMIN", "PRCP"]
        }

        datatypes = datatypes_map.get(data_type, ["TMAX", "TMIN"])

        # Laske päivämääräväli (jos ei annettu)
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if not start_date:
            start_dt = datetime.now() - timedelta(days=365)
            start_date = start_dt.strftime("%Y-%m-%d")

        try:
            # Step 1: Hae lähimmät asemat (jos koordinaatit annettu)
            station_id = None
            if latitude and longitude:
                station_id = self._find_nearest_station(latitude, longitude)

            # Step 2: Jos asema löytyi, hae data
            if station_id:
                return self._get_station_data(
                    station_id=station_id,
                    datatypes=datatypes,
                    start_date=start_date,
                    end_date=end_date,
                    location=location
                )
            else:
                # Fallback: Hae maatasolla (käytä FIPS-koodia Euroopalle)
                if self.logger:
                    self.logger.info(
                        "NOAA: No nearby station found, using global summary",
                        location=location
                    )
                return self._get_global_summary(location, start_date, end_date)

        except requests.RequestException as e:
            if self.logger:
                self.logger.error(
                    "NOAA API error",
                    error=str(e),
                    location=location
                )
            return None

    def _find_nearest_station(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 50
    ) -> Optional[str]:
        """
        Etsi lähin NOAA-sääasema koordinaattien perusteella

        Args:
            latitude: Leveyspiiri
            longitude: Pituuspiiri
            radius_km: Hakusäde kilometreinä

        Returns:
            Station ID tai None
        """
        endpoint = f"{self.api_url}/stations"

        # NOAA API käyttää extent-parametria (min_lat, min_lon, max_lat, max_lon)
        # Laske karkeasti ~50km säde
        lat_delta = 0.5  # ~50km
        lon_delta = 0.7

        try:
            start_time = time.time()

            params = {
                "datasetid": "GHCND",
                "extent": f"{latitude - lat_delta},{longitude - lon_delta},{latitude + lat_delta},{longitude + lon_delta}",
                "limit": 5,
                "sortfield": "name"
            }

            response = self.session.get(
                endpoint,
                params=params,
                timeout=30
            )

            duration_ms = (time.time() - start_time) * 1000

            if self.logger:
                self.logger.info(
                    "NOAA stations search",
                    status_code=response.status_code,
                    duration_ms=duration_ms
                )

            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])

                if results:
                    # Ota ensimmäinen asema
                    station = results[0]
                    station_id = station.get("id")

                    if self.logger:
                        self.logger.info(
                            f"NOAA: Found station {station.get('name', 'Unknown')}",
                            station_id=station_id
                        )

                    return station_id

            return None

        except Exception as e:
            if self.logger:
                self.logger.warning(f"NOAA station search failed: {e}")
            return None

    def _get_station_data(
        self,
        station_id: str,
        datatypes: List[str],
        start_date: str,
        end_date: str,
        location: str
    ) -> Optional[Dict[str, Any]]:
        """
        Hae dataa tietyltä asemalta

        Args:
            station_id: Aseman ID
            datatypes: Lista datatyypeistä (TMAX, TMIN, PRCP, etc.)
            start_date: Alkupäivä
            end_date: Loppupäivä
            location: Paikkakunnan nimi

        Returns:
            Dictionary dataa
        """
        endpoint = f"{self.api_url}/data"

        try:
            start_time = time.time()

            params = {
                "datasetid": "GHCND",
                "stationid": station_id,
                "datatypeid": datatypes,
                "startdate": start_date,
                "enddate": end_date,
                "units": "metric",
                "limit": 1000  # Max results
            }

            response = self.session.get(
                endpoint,
                params=params,
                timeout=30
            )

            duration_ms = (time.time() - start_time) * 1000

            if self.logger:
                self.logger.info(
                    "NOAA data fetch",
                    station=station_id,
                    status_code=response.status_code,
                    duration_ms=duration_ms
                )

            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])

            # Analysoi tulokset
            if results:
                temps_max = [r["value"] for r in results if r.get("datatype") == "TMAX"]
                temps_min = [r["value"] for r in results if r.get("datatype") == "TMIN"]
                precip = [r["value"] for r in results if r.get("datatype") == "PRCP"]

                return {
                    "source": "NOAA",
                    "location": location,
                    "station": station_id,
                    "dataType": "climate_data",
                    "data": {
                        "maxTemperatures": temps_max[:30] if temps_max else [],
                        "minTemperatures": temps_min[:30] if temps_min else [],
                        "precipitation": precip[:30] if precip else [],
                        "avgMaxTemp": round(sum(temps_max) / len(temps_max), 2) if temps_max else None,
                        "avgMinTemp": round(sum(temps_min) / len(temps_min), 2) if temps_min else None,
                        "totalPrecip": round(sum(precip), 2) if precip else None,
                        "dataPoints": len(results)
                    },
                    "dateRange": {
                        "start": start_date,
                        "end": end_date
                    },
                    "timestamp": datetime.now().isoformat()
                }

            return None

        except Exception as e:
            if self.logger:
                self.logger.error(f"NOAA data fetch failed: {e}")
            return None

    def _get_global_summary(
        self,
        location: str,
        start_date: str,
        end_date: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fallback: Hae globaali yhteenveto kun asemaa ei löydy

        Returns:
            Yksinkertainen placeholder-vastaus
        """
        if self.logger:
            self.logger.info(
                f"NOAA: Using global summary fallback for {location}"
            )

        # Palauta placeholder joka ilmaisee että data ei ole saatavilla tälle alueelle
        return {
            "source": "NOAA",
            "location": location,
            "dataType": "global_summary",
            "data": {
                "status": "No nearby weather stations found",
                "note": "NOAA GHCND data is primarily available for US locations. For European locations, use Open-Meteo or NASA POWER instead."
            },
            "dateRange": {
                "start": start_date,
                "end": end_date
            },
            "timestamp": datetime.now().isoformat()
        }


class NASAPowerClient:
    """
    NASA POWER API -asiakas (ilmainen, ei vaadi API-avainta)

    POWER = Prediction Of Worldwide Energy Resources
    Hakee aurinko- ja meteorologista dataa maataloudelle ja energialle.

    Dokumentaatio: https://power.larc.nasa.gov/docs/
    """

    def __init__(
        self,
        api_url: str = "https://power.larc.nasa.gov/api/temporal/daily/point",
        logger: Optional[BoundLogger] = None
    ):
        """
        Alusta NASA POWER -asiakas

        Args:
            api_url: API:n base URL
            logger: Logger
        """
        self.api_url = api_url.rstrip("/")
        self.logger = logger
        self.session = requests.Session()

        if self.logger:
            self.logger.info("NASA POWER client initialized (no API key required)")

    def get_climate_data(
        self,
        latitude: float,
        longitude: float,
        days_back: int = 30
    ) -> Optional[Dict[str, Any]]:
        """
        Hae ilmasto- ja energiadataa NASA POWER:lta

        Args:
            latitude: Leveyspiiri
            longitude: Pituuspiiri
            days_back: Montako päivää historiaa (max 365)

        Returns:
            Dictionary dataa tai None
        """
        # Laske päivämääräväli
        end_date = datetime.now()
        start_date = end_date - timedelta(days=min(days_back, 365))

        # POWER parametrit ilmastolle
        parameters = [
            "T2M",           # Temperature at 2 Meters
            "T2M_MAX",       # Maximum Temperature at 2 Meters
            "T2M_MIN",       # Minimum Temperature at 2 Meters
            "PRECTOTCORR",   # Precipitation Corrected
            "WS10M",         # Wind Speed at 10 Meters
            "ALLSKY_SFC_SW_DWN"  # Solar radiation
        ]

        try:
            start_time = time.time()

            # NASA POWER käyttää eri URL-rakennetta
            params = {
                "parameters": ",".join(parameters),
                "community": "RE",  # Renewable Energy
                "longitude": longitude,
                "latitude": latitude,
                "start": start_date.strftime("%Y%m%d"),
                "end": end_date.strftime("%Y%m%d"),
                "format": "JSON"
            }

            response = self.session.get(
                self.api_url,
                params=params,
                timeout=60
            )

            duration_ms = (time.time() - start_time) * 1000

            if self.logger:
                self.logger.info(
                    "NASA POWER API call",
                    endpoint=self.api_url,
                    status_code=response.status_code,
                    duration_ms=duration_ms
                )

            response.raise_for_status()
            data = response.json()

            # Parsea data
            properties = data.get("properties", {})
            parameter_data = properties.get("parameter", {})

            if parameter_data:
                # Laske keskiarvot
                temps = list(parameter_data.get("T2M", {}).values())
                temps_max = list(parameter_data.get("T2M_MAX", {}).values())
                temps_min = list(parameter_data.get("T2M_MIN", {}).values())
                precip = list(parameter_data.get("PRECTOTCORR", {}).values())
                wind = list(parameter_data.get("WS10M", {}).values())
                solar = list(parameter_data.get("ALLSKY_SFC_SW_DWN", {}).values())

                # Filtteröi -999 arvot (puuttuva data)
                temps = [t for t in temps if t != -999]
                temps_max = [t for t in temps_max if t != -999]
                precip = [p for p in precip if p != -999]
                wind = [w for w in wind if w != -999]
                solar = [s for s in solar if s != -999]

                if temps:
                    avg_temp = sum(temps) / len(temps)
                    max_temp = max(temps_max) if temps_max else None
                    total_precip = sum(precip) if precip else 0
                    avg_wind = sum(wind) / len(wind) if wind else 0
                    avg_solar = sum(solar) / len(solar) if solar else 0

                    return {
                        "source": "NASA POWER",
                        "latitude": latitude,
                        "longitude": longitude,
                        "data": {
                            "avgTemperature": round(avg_temp, 2),
                            "maxTemperature": round(max_temp, 2) if max_temp else None,
                            "totalPrecipitation": round(total_precip, 2),
                            "avgWindSpeed": round(avg_wind, 2),
                            "avgSolarRadiation": round(avg_solar, 2),
                            "daysAnalyzed": len(temps),
                            "unit": {
                                "temperature": "°C",
                                "precipitation": "mm/day",
                                "windSpeed": "m/s",
                                "solar": "kWh/m²/day"
                            }
                        },
                        "timestamp": datetime.now().isoformat()
                    }

            return None

        except requests.RequestException as e:
            if self.logger:
                self.logger.error(
                    "NASA POWER API error",
                    error=str(e),
                    latitude=latitude,
                    longitude=longitude
                )
            return None



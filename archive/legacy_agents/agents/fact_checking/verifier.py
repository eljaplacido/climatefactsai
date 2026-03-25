"""
Claim Verifier - GPT-4o -pohjainen väitteiden todentaja

Analysoi väitteet useista data-lähteistä ja tekee todennuspäätöksen.
"""

import json
from typing import Dict, Any, List, Optional

from openai import OpenAI
from structlog.stdlib import BoundLogger
from .perplexity_client import PerplexityClient


class ClaimVerifier:
    """
    Väitteiden todentaja GPT-4o:lla
    
    Käyttää GPT-4o:ta analysoimaan väitteitä vastaan kerättyä dataa
    ja tuottamaan strukturoidun todennusraportin.
    """
    
    SYSTEM_PROMPT = """You are a meticulous climate fact-checking agent.

Your task is to analyze climate-related claims and verify them against authoritative scientific data sources. You must be objective, analytical, and rigorous.

For each claim, you will receive:
1. The claim text
2. Context from the source article
3. Data from ClimateCheck API (risk scores)
4. Data from NOAA (historical climate data)
5. Data from NASA (satellite data) - if available

Your analysis must:
- Be based SOLELY on the provided data sources
- Assign a verification status: VERIFIED, UNVERIFIED, MISLEADING, LACKS_CONTEXT, or FALSE
- Provide a confidence score (0.0 to 1.0)
- List specific evidence from the data sources
- Give a brief justification (2-3 sentences maximum)

Respond in JSON format with this structure:
{
  "status": "VERIFIED|UNVERIFIED|MISLEADING|LACKS_CONTEXT|FALSE",
  "confidence": 0.0-1.0,
  "evidence": [
    {
      "sourceName": "ClimateCheck|NOAA|NASA",
      "sourceUrl": "url_to_data",
      "dataPoint": "specific measurement or finding"
    }
  ],
  "justification": "Brief explanation of verification result"
}
"""
    
    def __init__(
        self,
        openai_api_key: str,
        model: str = "gpt-4o",
        logger: Optional[BoundLogger] = None,
        perplexity_api_key: Optional[str] = None
    ):
        """
        Alusta verifier
        
        Args:
            openai_api_key: OpenAI API-avain
            model: LLM-malli (gpt-4o)
            logger: Logger
            perplexity_api_key: Perplexity API-avain (optional)
        """
        self.client = OpenAI(api_key=openai_api_key)
        self.model = model
        self.logger = logger
        
        # Perplexity-client (jos API-avain annettu)
        self.perplexity = None
        if perplexity_api_key:
            self.perplexity = PerplexityClient(perplexity_api_key)
            if self.logger:
                self.logger.info("Perplexity integration enabled")
        
        if self.logger:
            self.logger.info(
                "ClaimVerifier initialized",
                model=model,
                perplexity_enabled=self.perplexity is not None
            )
    
    def verify_claim(
        self,
        claim_text: str,
        claim_context: str,
        climatecheck_data: Optional[Dict[str, Any]] = None,
        noaa_data: Optional[Dict[str, Any]] = None,
        nasa_data: Optional[Dict[str, Any]] = None,
        location: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Todenna väite (käyttää Perplexityä jos saatavilla, muuten GPT-4o)
        
        Args:
            claim_text: Väitteen teksti
            claim_context: Väitteen konteksti
            climatecheck_data: ClimateCheck API -data
            noaa_data: NOAA API -data
            nasa_data: NASA API -data
            location: Maantieteellinen sijainti
        
        Returns:
            Todennustulos-dictionary
        """
        
        # Jos Perplexity on käytössä, käytä sitä ensisijaisesti
        if self.perplexity:
            if self.logger:
                self.logger.info("Using Perplexity for fact-checking", claim=claim_text[:50])
            
            try:
                perplexity_result = self.perplexity.verify_claim(
                    claim=claim_text,
                    context=claim_context,
                    location=location
                )
                
                # Muunna Perplexity-tulos standardimuotoon
                status_map = {
                    'TRUE': 'VERIFIED',
                    'FALSE': 'FALSE',
                    'PARTIALLY_TRUE': 'MISLEADING',
                    'DISPUTED': 'LACKS_CONTEXT'
                }
                
                return {
                    'status': status_map.get(perplexity_result.get('verdict', 'UNKNOWN'), 'UNVERIFIED'),
                    'confidence': perplexity_result.get('confidence', 0.5),
                    'evidence': [
                        {
                            'sourceName': 'Perplexity AI',
                            'sourceUrl': source,
                            'dataPoint': 'Real-time web search result'
                        }
                        for source in perplexity_result.get('sources', [])
                    ],
                    'justification': perplexity_result.get('explanation', ''),
                    'perplexity_citations': perplexity_result.get('citations', [])
                }
                
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Perplexity verification failed, falling back to GPT-4o: {e}")
        
        # Fallback: Käytä GPT-4o:ta perinteisellä tavalla
        # Rakenna prompt
        user_prompt = self._build_verification_prompt(
            claim_text=claim_text,
            claim_context=claim_context,
            climatecheck_data=climatecheck_data,
            noaa_data=noaa_data,
            nasa_data=nasa_data
        )
        
        try:
            # Kutsu GPT-4o
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2,  # Matala lämpötila -> deterministic
                max_tokens=1000
            )
            
            # Parsea vastaus
            result_json = response.choices[0].message.content
            result = json.loads(result_json)
            
            # Log LLM-kutsu
            if self.logger:
                self.log_llm_interaction(
                    model=self.model,
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_cost_usd=self._calculate_cost(response.usage)
                )
            
            # Validoi ja palauta
            return self._validate_result(result)
            
        except Exception as e:
            if self.logger:
                self.logger.error(
                    "Verification failed",
                    error=str(e),
                    claim_text=claim_text[:100]
                )
            
            # Fallback-vastaus
            return {
                "status": "UNVERIFIED",
                "confidence": 0.0,
                "evidence": [],
                "justification": f"Verification failed due to error: {str(e)}"
            }
    
    def _build_verification_prompt(
        self,
        claim_text: str,
        claim_context: str,
        climatecheck_data: Optional[Dict[str, Any]],
        noaa_data: Optional[Dict[str, Any]],
        nasa_data: Optional[Dict[str, Any]]
    ) -> str:
        """
        Rakenna verification-prompt
        
        Args:
            claim_text: Väitteen teksti
            claim_context: Konteksti
            climatecheck_data: ClimateCheck-data
            noaa_data: NOAA-data
            nasa_data: NASA-data
        
        Returns:
            Prompt-string
        """
        prompt_parts = []
        
        # Väite
        prompt_parts.append("CLAIM TO VERIFY:")
        prompt_parts.append(f'"{claim_text}"')
        prompt_parts.append("")
        
        # Konteksti
        if claim_context:
            prompt_parts.append("CONTEXT:")
            prompt_parts.append(claim_context[:500])  # Rajoita pituus
            prompt_parts.append("")
        
        # Data-lähteet
        prompt_parts.append("AVAILABLE DATA SOURCES:")
        prompt_parts.append("")
        
        # ClimateCheck
        if climatecheck_data:
            prompt_parts.append("1. ClimateCheck API:")
            prompt_parts.append(f"   - Hazard Type: {climatecheck_data.get('hazardType', 'N/A')}")
            prompt_parts.append(f"   - Risk Score: {climatecheck_data.get('riskScore', 'N/A')}/100")
            prompt_parts.append(f"   - Confidence: {climatecheck_data.get('confidence', 'N/A')}")
            prompt_parts.append("")
        else:
            prompt_parts.append("1. ClimateCheck API: No data available")
            prompt_parts.append("")
        
        # NOAA
        if noaa_data:
            prompt_parts.append("2. NOAA API:")
            prompt_parts.append(f"   - Location: {noaa_data.get('location', 'N/A')}")
            prompt_parts.append(f"   - Data Type: {noaa_data.get('dataType', 'N/A')}")
            results = noaa_data.get('results', [])
            if results:
                prompt_parts.append(f"   - Results: {len(results)} data points available")
                # Lisää muutama esimerkki
                for result in results[:3]:
                    prompt_parts.append(f"     • {result}")
            prompt_parts.append("")
        else:
            prompt_parts.append("2. NOAA API: No data available")
            prompt_parts.append("")
        
        # NASA
        if nasa_data:
            prompt_parts.append("3. NASA API:")
            prompt_parts.append(f"   - Temperature: {nasa_data.get('temperature', 'N/A')}")
            prompt_parts.append("")
        else:
            prompt_parts.append("3. NASA API: No data available")
            prompt_parts.append("")
        
        # Ohjeet
        prompt_parts.append("INSTRUCTIONS:")
        prompt_parts.append("Analyze the claim against the available data.")
        prompt_parts.append("Provide your verification in JSON format as specified.")
        
        return "\n".join(prompt_parts)
    
    def _validate_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validoi ja normalisoi todennustulos
        
        Args:
            result: GPT-4o:n palauttama JSON
        
        Returns:
            Validoitu ja normalisoitu tulos
        """
        # Varmista että kaikki vaaditut kentät ovat olemassa
        valid_statuses = ["VERIFIED", "UNVERIFIED", "MISLEADING", "LACKS_CONTEXT", "FALSE"]
        
        status = result.get("status", "UNVERIFIED")
        if status not in valid_statuses:
            status = "UNVERIFIED"
        
        confidence = result.get("confidence", 0.5)
        confidence = max(0.0, min(1.0, float(confidence)))  # Clamp 0-1
        
        evidence = result.get("evidence", [])
        if not isinstance(evidence, list):
            evidence = []
        
        justification = result.get("justification", "No justification provided")
        
        return {
            "status": status,
            "confidence": confidence,
            "evidence": evidence,
            "justification": justification
        }
    
    def _calculate_cost(self, usage: Any) -> float:
        """
        Laske LLM-kutsun hinta
        
        Args:
            usage: OpenAI usage-objekti
        
        Returns:
            Kustannus USD:na
        """
        # GPT-4o pricing (per 1K tokens)
        INPUT_PRICE = 0.005
        OUTPUT_PRICE = 0.015
        
        input_cost = (usage.prompt_tokens / 1000) * INPUT_PRICE
        output_cost = (usage.completion_tokens / 1000) * OUTPUT_PRICE
        
        return input_cost + output_cost
    
    def log_llm_interaction(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_cost_usd: float
    ):
        """
        Loggaa LLM-interaktio
        
        Args:
            model: Mallin nimi
            prompt_tokens: Prompt-tokenien määrä
            completion_tokens: Vastaus-tokenien määrä
            total_cost_usd: Kokonaiskustannus
        """
        if self.logger:
            self.logger.info(
                "LLM interaction",
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                total_cost_usd=round(total_cost_usd, 6)
            )


if __name__ == "__main__":
    # Testaa verifier (vaatii OPENAI_API_KEY-ympäristömuuttujan)
    import os
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY not set")
        exit(1)
    
    verifier = ClaimVerifier(openai_api_key=api_key)
    
    test_claim = "Helsingin lämpötila on noussut 2 astetta viimeisen 50 vuoden aikana."
    test_context = "Ilmatieteen laitoksen tutkimus osoittaa..."
    
    test_climatecheck = {
        "hazardType": "heat",
        "riskScore": 75,
        "confidence": 0.85
    }
    
    result = verifier.verify_claim(
        claim_text=test_claim,
        claim_context=test_context,
        climatecheck_data=test_climatecheck
    )
    
    print("Verification result:")
    print(json.dumps(result, indent=2))



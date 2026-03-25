"""
Claim Extractor - Väitteiden tunnistaminen NLP:llä

Käyttää spaCy:ta entiteettien ja väitteiden tunnistamiseen.
"""

import re
from typing import List, Dict, Any, Optional
from uuid import uuid4

from structlog.stdlib import BoundLogger


class ClaimExtractor:
    """
    Väitteiden ekstraktorikohta
    
    Tunnistaa todennettavissa olevia väitteitä artikkelitekstistä.
    """
    
    def __init__(self, logger: Optional[BoundLogger] = None):
        """
        Alusta claim extractor
        
        Args:
            logger: Logger
        """
        self.logger = logger
        
        # Lataa spaCy-malli (suomi tai englanti)
        try:
            import spacy
            try:
                self.nlp = spacy.load("fi_core_news_sm")
            except OSError:
                # Fallback englanninkieliseen malliin
                self.nlp = spacy.load("en_core_web_sm")
                if self.logger:
                    self.logger.warning("Finnish spaCy model not found, using English")
        except ImportError:
            self.nlp = None
            if self.logger:
                self.logger.warning("spaCy not installed, using pattern-based extraction")
        
        # Väitemalleja (regex-patternit)
        self.claim_patterns = [
            # Numeerinen väite
            r"(\d+(?:[.,]\d+)?)\s*(prosentti|%|astett?a|metriä|vuoteen|mennessä)",
            
            # Projektioväite
            r"(nousee|laskee|kasvaa|pienenee|saavuttaa|ylittää)\s+(?:\w+\s+){0,3}(\d+)",
            
            # Vertailuväite
            r"(korkeampi|matalampi|suurempi|pienempi|enemmän|vähemmän)\s+kuin",
            
            # Ennusteväite
            r"(ennusteen mukaan|arvioiden mukaan|tutkimuksen mukaan|raportin mukaan)",
            
            # Tieteellinen väite
            r"(tutkimus osoittaa|tutkijat toteavat|tiedemiehet varoittavat)",
        ]
        
        if self.logger:
            self.logger.info("ClaimExtractor initialized")
    
    def extract_claims(
        self,
        text: str,
        location: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Tunnista väitteet tekstistä
        
        Args:
            text: Artikkelin teksti
            location: Paikkatieto (kontekstia varten)
        
        Returns:
            Lista väite-dictionaryja
        """
        claims = []
        
        # Jaa teksti lauseiksi
        sentences = self._split_into_sentences(text)
        
        for sentence in sentences:
            # Tarkista onko lause väite
            if self._is_claim(sentence):
                claim_data = self._create_claim(
                    claim_text=sentence,
                    context=text,
                    location=location
                )
                claims.append(claim_data)
        
        if self.logger:
            self.logger.debug(f"Extracted {len(claims)} claims from text")
        
        return claims
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """
        Jaa teksti lauseiksi
        
        Args:
            text: Teksti
        
        Returns:
            Lista lauseita
        """
        if self.nlp:
            # Käytä spaCy:ta
            doc = self.nlp(text)
            return [sent.text.strip() for sent in doc.sents]
        else:
            # Yksinkertainen regex-pohjainen jako
            sentences = re.split(r'[.!?]+', text)
            return [s.strip() for s in sentences if len(s.strip()) > 20]
    
    def _is_claim(self, sentence: str) -> bool:
        """
        Tarkista onko lause todennettavissa oleva väite
        
        Args:
            sentence: Lause
        
        Returns:
            True jos on väite
        """
        # Tarkista patterneja vasten
        for pattern in self.claim_patterns:
            if re.search(pattern, sentence, re.IGNORECASE):
                return True
        
        # Lisäkriteerejä
        # - Sisältää numeron
        if re.search(r'\d+', sentence):
            # - Sisältää ilmastotermin
            climate_terms = [
                'ilmasto', 'climate', 'lämpötila', 'temperature',
                'päästö', 'emission', 'hiilidioksidi', 'co2',
                'merenpinta', 'sea level', 'sää', 'weather',
                'kuivuus', 'drought', 'tulva', 'flood'
            ]
            if any(term in sentence.lower() for term in climate_terms):
                return True
        
        return False
    
    def _create_claim(
        self,
        claim_text: str,
        context: str,
        location: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Luo strukturoitu claim-dictionary
        
        Args:
            claim_text: Väitteen teksti
            context: Ympäröivä konteksti
            location: Paikkatieto
        
        Returns:
            Claim-dictionary discovery_to_factcheck.json -skeeman mukaisesti
        """
        # Tunnista entiteetit
        entities = self._extract_entities(claim_text)
        
        # Määritä väitteen tyyppi
        claim_type = self._classify_claim_type(claim_text)
        
        # Luo claim-objekti
        claim = {
            "claimId": str(uuid4()),
            "claimText": claim_text,
            "context": self._extract_context(claim_text, context),
            "claimType": claim_type,
            "entities": entities
        }
        
        # Lisää paikkatieto jos saatavilla
        if location:
            claim["location"] = {
                "name": location.get("name"),
                "latitude": location.get("latitude"),
                "longitude": location.get("longitude"),
                "country": location.get("country")
            }
        
        return claim
    
    def _extract_entities(self, text: str) -> List[Dict[str, str]]:
        """
        Tunnista nimetyt entiteetit (NER)
        
        Args:
            text: Teksti
        
        Returns:
            Lista entiteettejä
        """
        entities = []
        
        if self.nlp:
            doc = self.nlp(text)
            for ent in doc.ents:
                entities.append({
                    "text": ent.text,
                    "type": ent.label_
                })
        
        return entities
    
    def _classify_claim_type(self, claim_text: str) -> str:
        """
        Luokittele väitteen tyyppi
        
        Args:
            claim_text: Väitteen teksti
        
        Returns:
            Väitteen tyyppi (enum)
        """
        text_lower = claim_text.lower()
        
        # Faktadataväite (sisältää konkreettisia numeroita)
        if re.search(r'\d+(?:[.,]\d+)?', claim_text):
            if any(word in text_lower for word in ['nousee', 'laskee', 'kasvaa', 'ennustaa', 'projekti', 'vuoteen', 'mennessä']):
                return "prediction"
            elif any(word in text_lower for word in ['mittaus', 'mitattu', 'tilasto', 'data']):
                return "factual_data"
            else:
                return "statistical_claim"
        
        # Politiikkaväite
        if any(word in text_lower for word in ['hallitus', 'päätös', 'laki', 'säädös', 'policy']):
            return "policy_statement"
        
        # Tieteellinen väite
        if any(word in text_lower for word in ['tutkimus', 'tutkijat', 'tiedemiehet', 'tiede', 'research', 'study']):
            return "scientific_claim"
        
        # Tapahtumaväraportti
        if any(word in text_lower for word in ['tapahtui', 'sattui', 'tilaisuudessa', 'occurred']):
            return "event_report"
        
        return "factual_data"  # Default
    
    def _extract_context(
        self,
        claim_text: str,
        full_text: str,
        context_window: int = 200
    ) -> str:
        """
        Ekstraktoi ympäröivä konteksti väitteelle
        
        Args:
            claim_text: Väitteen teksti
            full_text: Koko artikkelin teksti
            context_window: Merkkien määrä kummallekin puolelle
        
        Returns:
            Konteksti-string
        """
        # Etsi väitteen sijainti
        pos = full_text.find(claim_text)
        
        if pos == -1:
            return claim_text
        
        # Ekstraktoi ympäröivä teksti
        start = max(0, pos - context_window)
        end = min(len(full_text), pos + len(claim_text) + context_window)
        
        context = full_text[start:end]
        
        # Lisää "..." jos katkaistiin
        if start > 0:
            context = "..." + context
        if end < len(full_text):
            context = context + "..."
        
        return context.strip()


if __name__ == "__main__":
    # Testaa claim extractor
    extractor = ClaimExtractor()
    
    test_text = """
    Helsingin lämpötila on noussut 2 astetta viimeisen 50 vuoden aikana.
    Tutkimuksen mukaan merenpinnan nousu voi ylittää metrin vuoteen 2100 mennessä.
    Ilmatieteen laitos raportoi, että viime vuosi oli kuumin mitattu vuosi.
    """
    
    claims = extractor.extract_claims(test_text)
    
    print(f"Löydettiin {len(claims)} väitettä:")
    for claim in claims:
        print(f"- {claim['claimText']}")
        print(f"  Tyyppi: {claim['claimType']}")



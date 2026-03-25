"""
Perplexity AI client for fact-checking and research

Perplexity on erinomainen työkalu faktatarkistukseen koska:
1. Se hakee ajantasaista tietoa internetistä
2. Antaa lähteet väitteille
3. Voi tarkistaa monimutkaisia ilmastoväitteitä
"""

import requests
from typing import Dict, List, Optional, Any
from datetime import datetime


class PerplexityClient:
    """
    Perplexity AI API client
    
    Käyttö:
        client = PerplexityClient(api_key="pplx-xxx")
        result = client.verify_claim("Arktisen jään määrä on vähentynyt 40%")
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.perplexity.ai"
        self.model = "sonar"
    
    def verify_claim(
        self,
        claim: str,
        context: Optional[str] = None,
        location: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Tarkista väite Perplexityn avulla
        
        Args:
            claim: Tarkistettava väite
            context: Lisäkonteksti (artikkelin ote)
            location: Maantieteellinen sijainti
        
        Returns:
            {
                'verified': bool,
                'confidence': float,
                'explanation': str,
                'sources': List[str],
                'citations': List[Dict]
            }
        """
        
        # Rakenna prompt
        prompt = f"""You are a climate fact-checker. Verify the following claim using reliable, up-to-date sources.

Claim to verify: "{claim}"
"""
        
        if context:
            prompt += f"\nContext: {context}\n"
        
        if location:
            prompt += f"\nLocation: {location}\n"
        
        prompt += """
Please analyze:
1. Is this claim factually accurate?
2. What is your confidence level (0-100%)?
3. What sources support or refute this claim?
4. Provide specific citations and data.

Respond in this format:
VERDICT: [TRUE/FALSE/PARTIALLY_TRUE/DISPUTED]
CONFIDENCE: [0-100]%
EXPLANATION: [Your detailed analysis]
SOURCES: [List key sources]
"""
        
        # API-kutsu
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.2,
            "max_tokens": 1000
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Parsitaan vastaus
            content = data['choices'][0]['message']['content']
            citations = data.get('citations', [])
            
            # Yksinkertainen parsing
            verdict = self._extract_verdict(content)
            confidence = self._extract_confidence(content)
            explanation = self._extract_explanation(content)
            sources = self._extract_sources(content, citations)
            
            return {
                'verified': verdict in ['TRUE', 'PARTIALLY_TRUE'],
                'verdict': verdict,
                'confidence': confidence,
                'explanation': explanation,
                'sources': sources,
                'citations': citations,
                'raw_response': content,
                'checked_at': datetime.utcnow().isoformat()
            }
            
        except requests.exceptions.RequestException as e:
            return {
                'verified': False,
                'verdict': 'ERROR',
                'confidence': 0.0,
                'explanation': f"Perplexity API error: {str(e)}",
                'sources': [],
                'citations': [],
                'error': str(e)
            }
    
    def _extract_verdict(self, text: str) -> str:
        """Poimii verdiktin tekstistä"""
        text_upper = text.upper()
        
        if 'VERDICT: TRUE' in text_upper or 'VERDICT:TRUE' in text_upper:
            return 'TRUE'
        elif 'VERDICT: FALSE' in text_upper or 'VERDICT:FALSE' in text_upper:
            return 'FALSE'
        elif 'VERDICT: PARTIALLY_TRUE' in text_upper or 'PARTIALLY TRUE' in text_upper:
            return 'PARTIALLY_TRUE'
        elif 'VERDICT: DISPUTED' in text_upper or 'DISPUTED' in text_upper:
            return 'DISPUTED'
        else:
            return 'UNKNOWN'
    
    def _extract_confidence(self, text: str) -> float:
        """Poimii luottamusprosentin"""
        import re
        
        # Etsi "CONFIDENCE: 85%" tai "85%"
        match = re.search(r'CONFIDENCE:\s*(\d+)%?', text, re.IGNORECASE)
        if match:
            return float(match.group(1)) / 100.0
        
        # Etsi pelkkä prosentti
        match = re.search(r'(\d+)%', text)
        if match:
            return float(match.group(1)) / 100.0
        
        return 0.5  # Default 50%
    
    def _extract_explanation(self, text: str) -> str:
        """Poimii selityksen"""
        import re
        
        match = re.search(r'EXPLANATION:\s*(.+?)(?=SOURCES:|$)', text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        # Jos ei löydy, palauta koko teksti
        return text.strip()
    
    def _extract_sources(self, text: str, citations: List) -> List[str]:
        """Poimii lähteet"""
        sources = []
        
        # Käytä Perplexityn citationeja jos saatavilla
        if citations and isinstance(citations, list):
            for c in citations:
                if isinstance(c, dict):
                    sources.append(c.get('url', c.get('title', '')))
                elif isinstance(c, str):
                    sources.append(c)
        
        # Etsi myös tekstistä
        import re
        match = re.search(r'SOURCES:\s*(.+?)(?=\n\n|$)', text, re.DOTALL | re.IGNORECASE)
        if match:
            source_text = match.group(1)
            # Jaa riveittäin ja poista tyhjät
            text_sources = [s.strip('- ').strip() for s in source_text.split('\n') if s.strip()]
            sources.extend(text_sources)
        
        return list(set(sources))[:5]  # Max 5 uniikkia lähdettä


def test_perplexity():
    """Testaa Perplexity-integraatio"""
    import os
    
    api_key = os.getenv("PERPLEXITY_API_KEY", "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")
    
    client = PerplexityClient(api_key)
    
    # Testaa väite
    result = client.verify_claim(
        claim="Arktisen jään määrä on vähentynyt 40% vuodesta 1979",
        location="Arctic"
    )
    
    print("=" * 60)
    print("PERPLEXITY FACT-CHECK TEST")
    print("=" * 60)
    print(f"\nVerdict: {result['verdict']}")
    print(f"Confidence: {result['confidence']*100:.0f}%")
    print(f"\nExplanation:\n{result['explanation']}")
    print(f"\nSources: {len(result['sources'])}")
    for i, source in enumerate(result['sources'], 1):
        print(f"  {i}. {source}")
    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_perplexity()


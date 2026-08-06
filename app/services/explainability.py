# app/services/explainability.py
from typing import List, Dict

class Explainability:
    """Generate human-readable explanations for risk assessments"""
    
    def __init__(self):
        self.factor_explanations = {
            "Long call duration": {
                "explanation": "Extended call duration increases scam risk",
                "contribution": "High"
            },
            "Unknown caller": {
                "explanation": "Unverified caller identity is a common scam tactic",
                "contribution": "High"
            },
            "Video call": {
                "explanation": "Video calls are often used to intimidate victims",
                "contribution": "High"
            },
            "Low outgoing activity": {
                "explanation": "Isolation behavior detected - victim may be trapped",
                "contribution": "High"
            },
            "First-time caller": {
                "explanation": "No prior contact history with this number",
                "contribution": "Medium"
            }
        }
    
    def explain_risk(self, risk_factors: List[str], risk_score: float) -> Dict:
        explanations = []
        for factor in risk_factors:
            if factor in self.factor_explanations:
                explanations.append({
                    "factor": factor,
                    "explanation": self.factor_explanations[factor]["explanation"],
                    "contribution": self.factor_explanations[factor]["contribution"]
                })
        
        top_factors = [f['factor'] for f in explanations[:3]]
        summary = f"The combination of {', '.join(top_factors)} significantly increases the estimated scam risk."
        
        return {
            "risk_score": risk_score,
            "factors": explanations,
            "summary": summary,
            "recommendation": "Contact the person on an alternative number immediately."
        }
    
    def get_model_reasoning(self, risk_score: float, risk_factors: List[str]) -> Dict:
        explanations = self.explain_risk(risk_factors, risk_score)
        return {
            "model_decision": "SCAM_DETECTED" if risk_score > 50 else "NO_SCAM",
            "confidence": f"{risk_score}%",
            "reasoning": explanations["summary"],
            "contributing_factors": explanations["factors"]
        }
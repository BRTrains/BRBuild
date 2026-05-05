import logging
logger = logging.getLogger(__name__)

class Physics:
    def __init__(self):
        return

    def calculate_TE_coefficient(self, tractive_effort, weight):
        if tractive_effort is None or weight is None:
            raise ValueError(f"Tractive effort ({tractive_effort}) or weight ({weight}) is None. Cannot calculate TE coefficient.")
            return 0
        
        if tractive_effort < 1:
            return tractive_effort # Value in YAML already a coefficient (probably imported from existing code)
            
        gravity = 9.8
        target_TE = tractive_effort # Already in kN

        TE_coefficient = target_TE / weight / gravity

        if TE_coefficient > 1:
            logger.warning(f"Calculated TE coefficient {TE_coefficient} is greater than 1. This may indicate an error in the input data. Capping TE coefficient at 1.")
            TE_coefficient = 1 # Cap at 1, as it doesn't make sense to have a coefficient greater than 1 in this context

        return round(TE_coefficient, 5)

    def calculate_AD_coefficient(self, speed_mph):
        if speed_mph is None:
            raise ValueError("Speed is None. Cannot calculate AD coefficient.")
        speed_kmh = speed_mph * 1.60934
        AD_coefficient = 8 / speed_kmh # OpenTTD calculation, the 8 is a magic  number and has no basis in physics        
        return round(AD_coefficient,5)
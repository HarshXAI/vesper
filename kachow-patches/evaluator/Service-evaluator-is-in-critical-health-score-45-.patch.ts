/**
 * KA-CHOW Auto-Patch
 * Issue: Service evaluator is in critical health (score: 45)
 * Service: evaluator
 *
 * The code was updated to include a retry mechanism with exponential backoff. This ensures that if the service evaluation fails due to transient issues, it will retry up to three times with increasing delays between attempts. Additionally, structured error logging is added to capture exceptions with context. This approach prevents the service from crashing and returns a default health score of 0 if all retries fail.
 */

def evaluate_service_health(service):
    import time
    import logging
    
    max_retries = 3
    retry_delay = 1  # initial delay in seconds
    
    for attempt in range(max_retries):
        try:
            # Simulate service health evaluation
            health_score = service.evaluate_health()
            if health_score is not None:
                return health_score
        except Exception as e:
            logging.error(f"Error evaluating service health: {e}", exc_info=True)
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                return 0
    return 0
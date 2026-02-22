/**
 * KA-CHOW Auto-Patch
 * Issue: Service checkoutservice is in critical health (score: 45)
 * Service: checkoutservice
 *
 * The code was updated to include an AbortController to handle request timeouts, ensuring that requests do not hang indefinitely. A timeout of 10 seconds was set. An exponential backoff retry mechanism was implemented, allowing up to 3 retries with increasing delays between attempts. Proper error handling was added to log errors and rethrow them when necessary. This ensures that transient errors and network issues are managed effectively, improving the service's reliability.
 */

async function fetchWithRetry(url: string, options: RequestInit, retries = 3): Promise<Response> {
  const delay = (ms: number) => new Promise(res => setTimeout(res, ms));
  const exponentialBackoff = (attempt: number) => Math.pow(2, attempt) * 100;

  for (let attempt = 0; attempt <= retries; attempt++) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await fetch(url, { ...options, signal: controller.signal });
      clearTimeout(timeoutId);
      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }
      return response;
    } catch (error) {
      clearTimeout(timeoutId);
      console.error(`Attempt ${attempt + 1} failed:`, error);
      if (attempt < retries) {
        await delay(exponentialBackoff(attempt));
      } else {
        throw error;
      }
    }
  }
  throw new Error('Failed to fetch after retries');
}
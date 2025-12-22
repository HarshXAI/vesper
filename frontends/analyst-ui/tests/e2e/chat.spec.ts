import { test, expect, Page } from '@playwright/test';

/**
 * VESPER Analyst UI E2E Tests
 * Tests the chat interface with SSE streaming and citations
 */

// Test credentials - in CI, these come from environment
const TEST_USER = {
    email: process.env.TEST_USER_EMAIL || 'test@example.com',
    password: process.env.TEST_USER_PASSWORD || 'TestPassword123!',
};

// Helper to authenticate
async function authenticate(page: Page) {
    await page.goto('/');

    // Check if already authenticated
    const signInButton = page.getByRole('button', { name: /sign in/i });
    if (await signInButton.isVisible({ timeout: 2000 }).catch(() => false)) {
        // For testing purposes, we'll mock the auth
        // In real E2E, this would go through Cognito
        await page.evaluate(() => {
            // Mock session for testing
            sessionStorage.setItem('mock-auth', 'true');
        });

        await page.goto('/');
    }
}

test.describe('Analyst UI - Chat Flow', () => {
    test.beforeEach(async ({ page }) => {
        // Mock the API responses for testing
        await page.route('**/v1/ask', async (route) => {
            // Simulate SSE response
            const body = `data: {"token":"Based "}\n\ndata: {"token":"on "}\n\ndata: {"token":"the "}\n\ndata: {"token":"10-K "}\n\ndata: {"token":"filing, "}\n\ndata: {"token":"revenue "}\n\ndata: {"token":"increased "}\n\ndata: {"token":"15%."}\n\ndata: {"citation":{"id":"cite-1","text":"Revenue for fiscal year 2024 was $50B, up 15% YoY.","source":"Apple 10-K FY2024","document_id":"aapl-10k-2024","page":42,"score":0.95}}\n\ndata: {"metadata":{"trace_id":"abc123"}}\n\ndata: [DONE]\n\n`;

            await route.fulfill({
                status: 200,
                contentType: 'text/event-stream',
                body,
            });
        });
    });

    test('should display login screen when not authenticated', async ({ page }) => {
        await page.goto('/');

        // Should see login prompt
        await expect(page.getByText('VESPER')).toBeVisible();
        await expect(page.getByRole('button', { name: /sign in/i })).toBeVisible();
    });

    test('should show chat interface after login', async ({ page }) => {
        // Mock authentication
        await page.addInitScript(() => {
            // Mock next-auth session
            (window as any).__NEXT_AUTH_SESSION = {
                user: { email: 'test@example.com', tenantId: 'test-tenant' },
                accessToken: 'mock-token',
            };
        });

        await page.goto('/');

        // Wait for the chat input to be visible (indicates authenticated state)
        await expect(page.getByPlaceholder(/ask a question/i)).toBeVisible({ timeout: 5000 });
    });

    test('should stream response when asking a question', async ({ page }) => {
        // Mock authentication
        await page.addInitScript(() => {
            (window as any).__NEXT_AUTH_SESSION = {
                user: { email: 'test@example.com', tenantId: 'test-tenant' },
                accessToken: 'mock-token',
            };
        });

        await page.goto('/');

        // Type a question
        const input = page.getByPlaceholder(/ask a question/i);
        await input.fill('What was Apple\'s revenue in 2024?');

        // Submit
        await page.getByRole('button', { name: /send/i }).click();

        // Should show user message
        await expect(page.getByText("What was Apple's revenue in 2024?")).toBeVisible();

        // Should stream response
        await expect(page.getByText(/based on the 10-k filing/i)).toBeVisible({ timeout: 10000 });
        await expect(page.getByText(/revenue increased 15%/i)).toBeVisible();
    });

    test('should display citation chips after response', async ({ page }) => {
        await page.addInitScript(() => {
            (window as any).__NEXT_AUTH_SESSION = {
                user: { email: 'test@example.com', tenantId: 'test-tenant' },
                accessToken: 'mock-token',
            };
        });

        await page.goto('/');

        // Ask a question
        await page.getByPlaceholder(/ask a question/i).fill('Tell me about revenue');
        await page.getByRole('button', { name: /send/i }).click();

        // Wait for response to complete
        await expect(page.getByText(/sources/i)).toBeVisible({ timeout: 10000 });

        // Should show citation chip
        await expect(page.getByText('[1]')).toBeVisible();
        await expect(page.getByText(/apple 10-k/i)).toBeVisible();
    });

    test('should show citation preview on hover', async ({ page }) => {
        await page.addInitScript(() => {
            (window as any).__NEXT_AUTH_SESSION = {
                user: { email: 'test@example.com', tenantId: 'test-tenant' },
                accessToken: 'mock-token',
            };
        });

        await page.goto('/');

        // Ask a question and wait for response
        await page.getByPlaceholder(/ask a question/i).fill('Revenue info');
        await page.getByRole('button', { name: /send/i }).click();

        // Wait for citation to appear
        const citationChip = page.getByText('[1]');
        await expect(citationChip).toBeVisible({ timeout: 10000 });

        // Hover over citation
        await citationChip.hover();

        // Should show preview with citation text
        await expect(page.getByText(/revenue for fiscal year 2024/i)).toBeVisible();
        await expect(page.getByText(/page 42/i)).toBeVisible();
    });

    test('should copy response with citations', async ({ page }) => {
        await page.addInitScript(() => {
            (window as any).__NEXT_AUTH_SESSION = {
                user: { email: 'test@example.com', tenantId: 'test-tenant' },
                accessToken: 'mock-token',
            };
        });

        await page.goto('/');

        // Ask a question and wait for response
        await page.getByPlaceholder(/ask a question/i).fill('Revenue');
        await page.getByRole('button', { name: /send/i }).click();

        // Wait for response to complete
        await expect(page.getByText(/sources/i)).toBeVisible({ timeout: 10000 });

        // Click copy button
        const copyButton = page.getByRole('button', { name: /copy/i });
        await copyButton.click();

        // Should show check icon (indicating copied)
        await expect(page.locator('svg.lucide-check')).toBeVisible();

        // Verify clipboard content (if supported)
        const clipboardText = await page.evaluate(() => navigator.clipboard.readText());
        expect(clipboardText).toContain('References');
    });

    test('should show trace view when clicking view trace', async ({ page }) => {
        await page.addInitScript(() => {
            (window as any).__NEXT_AUTH_SESSION = {
                user: { email: 'test@example.com', tenantId: 'test-tenant' },
                accessToken: 'mock-token',
            };
        });

        await page.goto('/');

        // Ask a question
        await page.getByPlaceholder(/ask a question/i).fill('Test query');
        await page.getByRole('button', { name: /send/i }).click();

        // Wait for response with trace_id
        await expect(page.getByText(/view trace/i)).toBeVisible({ timeout: 10000 });

        // Click to show trace
        await page.getByText(/view trace/i).click();

        // Should show trace panel
        await expect(page.getByText('Trace Details')).toBeVisible();
        await expect(page.getByText('abc123')).toBeVisible();
    });

    test('should handle streaming errors gracefully', async ({ page }) => {
        // Override route to return error
        await page.route('**/v1/ask', async (route) => {
            await route.fulfill({
                status: 500,
                body: 'Internal Server Error',
            });
        });

        await page.addInitScript(() => {
            (window as any).__NEXT_AUTH_SESSION = {
                user: { email: 'test@example.com', tenantId: 'test-tenant' },
                accessToken: 'mock-token',
            };
        });

        await page.goto('/');

        // Ask a question
        await page.getByPlaceholder(/ask a question/i).fill('This will fail');
        await page.getByRole('button', { name: /send/i }).click();

        // Should show error message
        await expect(page.getByText(/error|failed|connection/i)).toBeVisible({ timeout: 10000 });
    });

    test('should stop streaming when stop button is clicked', async ({ page }) => {
        // Slow response to test stopping
        await page.route('**/v1/ask', async (route) => {
            const chunks = ['data: {"token":"Slow "}\n\n'];
            for (let i = 0; i < 10; i++) {
                chunks.push(`data: {"token":"word${i} "}\n\n`);
            }

            await route.fulfill({
                status: 200,
                contentType: 'text/event-stream',
                body: chunks.join(''),
            });
        });

        await page.addInitScript(() => {
            (window as any).__NEXT_AUTH_SESSION = {
                user: { email: 'test@example.com', tenantId: 'test-tenant' },
                accessToken: 'mock-token',
            };
        });

        await page.goto('/');

        // Ask a question
        await page.getByPlaceholder(/ask a question/i).fill('Long response');
        await page.getByRole('button', { name: /send/i }).click();

        // Should see loading indicator
        await expect(page.locator('.animate-spin')).toBeVisible();

        // Click stop button (the loading button acts as stop)
        await page.locator('.animate-spin').click();

        // Loading should stop
        await expect(page.locator('.animate-spin')).not.toBeVisible({ timeout: 5000 });
    });
});

test.describe('Analyst UI - Keyboard Navigation', () => {
    test('should submit on Enter key', async ({ page }) => {
        await page.addInitScript(() => {
            (window as any).__NEXT_AUTH_SESSION = {
                user: { email: 'test@example.com', tenantId: 'test-tenant' },
                accessToken: 'mock-token',
            };
        });

        await page.route('**/v1/ask', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'text/event-stream',
                body: 'data: {"token":"Response"}\n\ndata: [DONE]\n\n',
            });
        });

        await page.goto('/');

        const input = page.getByPlaceholder(/ask a question/i);
        await input.fill('Enter key test');
        await input.press('Enter');

        // Should submit and show response
        await expect(page.getByText('Enter key test')).toBeVisible();
        await expect(page.getByText('Response')).toBeVisible({ timeout: 5000 });
    });

    test('should allow multiline with Shift+Enter', async ({ page }) => {
        await page.addInitScript(() => {
            (window as any).__NEXT_AUTH_SESSION = {
                user: { email: 'test@example.com', tenantId: 'test-tenant' },
                accessToken: 'mock-token',
            };
        });

        await page.goto('/');

        const input = page.getByPlaceholder(/ask a question/i);
        await input.fill('Line 1');
        await input.press('Shift+Enter');
        await input.type('Line 2');

        // Should have multiline content
        const value = await input.inputValue();
        expect(value).toContain('Line 1');
        expect(value).toContain('Line 2');
    });
});

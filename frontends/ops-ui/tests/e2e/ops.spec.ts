import { test, expect } from '@playwright/test';

/**
 * VESPER Ops UI E2E Tests
 * Tests dashboard viewing, eval listing, and remediation triggering
 */

test.describe('Ops UI - Dashboard', () => {
    test.beforeEach(async ({ page }) => {
        // Mock authentication
        await page.addInitScript(() => {
            (window as any).__NEXT_AUTH_SESSION = {
                user: {
                    email: 'ops@example.com',
                    tenantId: 'test-tenant',
                    roles: ['ops', 'admin']
                },
                accessToken: 'mock-token',
            };
        });
    });

    test('should display dashboard with metric cards', async ({ page }) => {
        await page.goto('/');

        // Should show dashboard header
        await expect(page.getByText('Operations Dashboard')).toBeVisible();

        // Should show key metric cards
        await expect(page.getByText('API p95 Latency')).toBeVisible();
        await expect(page.getByText('Request Rate')).toBeVisible();
        await expect(page.getByText('Cache Hit Ratio')).toBeVisible();
        await expect(page.getByText('Daily Cost')).toBeVisible();
    });

    test('should show system status indicator', async ({ page }) => {
        await page.goto('/');

        // Should show "All Systems Operational" or similar
        await expect(page.getByText(/systems? operational/i)).toBeVisible();
    });

    test('should display evaluation metrics summary', async ({ page }) => {
        await page.goto('/');

        // Should show evaluation metrics section
        await expect(page.getByText('Latest Evaluation Metrics')).toBeVisible();
        await expect(page.getByText('Faithfulness')).toBeVisible();
        await expect(page.getByText('Relevance')).toBeVisible();
        await expect(page.getByText('Hallucination Rate')).toBeVisible();
    });

    test('should display recent alerts', async ({ page }) => {
        await page.goto('/');

        // Should show alerts section
        await expect(page.getByText('Recent Alerts')).toBeVisible();
    });

    test('should have working sidebar navigation', async ({ page }) => {
        await page.goto('/');

        // Click on Evaluations link
        await page.getByRole('link', { name: /evaluations/i }).click();
        await expect(page).toHaveURL(/\/evals/);

        // Click on Actions link
        await page.getByRole('link', { name: /actions/i }).click();
        await expect(page).toHaveURL(/\/actions/);

        // Click on Dashboard link
        await page.getByRole('link', { name: /dashboard/i }).click();
        await expect(page).toHaveURL('/');
    });
});

test.describe('Ops UI - Evaluations', () => {
    test.beforeEach(async ({ page }) => {
        await page.addInitScript(() => {
            (window as any).__NEXT_AUTH_SESSION = {
                user: {
                    email: 'ops@example.com',
                    tenantId: 'test-tenant',
                    roles: ['ops']
                },
                accessToken: 'mock-token',
            };
        });

        // Mock evals API
        await page.route('**/api/evals', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify([
                    {
                        id: 'eval-001',
                        timestamp: '2024-12-21T02:00:00Z',
                        status: 'success',
                        metrics: {
                            faithfulness: 0.94,
                            relevance: 0.88,
                            recall_at_10: 0.82,
                            ndcg_at_10: 0.79,
                            latency_p95_ms: 1850,
                            cost_usd: 12.45,
                        },
                        sample_count: 100,
                        mlflow_run_id: 'run-abc123',
                    },
                    {
                        id: 'eval-002',
                        timestamp: '2024-12-20T02:00:00Z',
                        status: 'failure',
                        metrics: {
                            faithfulness: 0.85,
                            relevance: 0.82,
                            recall_at_10: 0.75,
                            ndcg_at_10: 0.72,
                            latency_p95_ms: 2100,
                            cost_usd: 10.20,
                        },
                        sample_count: 100,
                        mlflow_run_id: 'run-def456',
                    },
                ]),
            });
        });
    });

    test('should display evaluation runs table', async ({ page }) => {
        await page.goto('/evals');

        // Should show evals page header
        await expect(page.getByText('Evaluation Runs')).toBeVisible();

        // Should show table headers
        await expect(page.getByText('Timestamp')).toBeVisible();
        await expect(page.getByText('Status')).toBeVisible();
        await expect(page.getByText('Faithfulness')).toBeVisible();
    });

    test('should show latest run metrics', async ({ page }) => {
        await page.goto('/evals');

        // Should show metric values from mock data
        await expect(page.getByText('0.94')).toBeVisible();
        await expect(page.getByText('0.88')).toBeVisible();
    });

    test('should filter by status', async ({ page }) => {
        await page.goto('/evals');

        // Click success filter
        await page.getByRole('button', { name: 'Success' }).click();

        // Should show only success runs
        await expect(page.getByText('Success', { exact: true })).toBeVisible();

        // Click failure filter
        await page.getByRole('button', { name: 'Failure' }).click();

        // Should show failure badge
        await expect(page.getByText('Failure', { exact: true })).toBeVisible();
    });

    test('should have refresh button', async ({ page }) => {
        await page.goto('/evals');

        const refreshButton = page.getByRole('button', { name: /refresh/i });
        await expect(refreshButton).toBeVisible();

        // Click refresh
        await refreshButton.click();

        // Should still show data after refresh
        await expect(page.getByText('Evaluation Runs')).toBeVisible();
    });

    test('should link to MLflow', async ({ page }) => {
        await page.goto('/evals');

        // Should have MLflow links
        const mlflowLink = page.getByRole('link', { name: /mlflow/i }).first();
        await expect(mlflowLink).toBeVisible();
    });
});

test.describe('Ops UI - Remediation Actions', () => {
    test.beforeEach(async ({ page }) => {
        await page.addInitScript(() => {
            (window as any).__NEXT_AUTH_SESSION = {
                user: {
                    email: 'ops@example.com',
                    tenantId: 'test-tenant',
                    roles: ['ops', 'admin']
                },
                accessToken: 'mock-token',
            };
        });
    });

    test('should display action cards', async ({ page }) => {
        await page.goto('/actions');

        // Should show actions page header
        await expect(page.getByText('Remediation Actions')).toBeVisible();

        // Should show action cards
        await expect(page.getByText('Re-embed Last 24h')).toBeVisible();
        await expect(page.getByText('Rechunk with New Params')).toBeVisible();
        await expect(page.getByText('Run Nightly Evaluation')).toBeVisible();
    });

    test('should show warning banner', async ({ page }) => {
        await page.goto('/actions');

        // Should show production warning
        await expect(page.getByText(/production impact/i)).toBeVisible();
    });

    test('should trigger DAG and show 202 Accepted', async ({ page }) => {
        // Mock DAG trigger API
        await page.route('**/api/trigger-dag', async (route) => {
            await route.fulfill({
                status: 202,
                contentType: 'application/json',
                body: JSON.stringify({
                    message: 'DAG triggered successfully',
                    dag_run_id: 'run-xyz789',
                }),
            });
        });

        await page.goto('/actions');

        // Find the first "Trigger DAG" button and click
        const triggerButton = page.getByRole('button', { name: /trigger dag/i }).first();
        await triggerButton.click();

        // Should show success toast
        await expect(page.getByText(/triggered successfully/i)).toBeVisible({ timeout: 5000 });

        // Should show in recent triggers
        await expect(page.getByText('202 Accepted')).toBeVisible();
    });

    test('should show trigger history', async ({ page }) => {
        await page.route('**/api/trigger-dag', async (route) => {
            await route.fulfill({
                status: 202,
                contentType: 'application/json',
                body: JSON.stringify({ dag_run_id: 'run-test' }),
            });
        });

        await page.goto('/actions');

        // Trigger a DAG
        await page.getByRole('button', { name: /trigger dag/i }).first().click();

        // Should show recent triggers section with the trigger
        await expect(page.getByText('Recent Triggers')).toBeVisible();
        await expect(page.getByText('202 Accepted')).toBeVisible();
    });

    test('should handle trigger failure gracefully', async ({ page }) => {
        // Mock DAG trigger failure
        await page.route('**/api/trigger-dag', async (route) => {
            await route.fulfill({
                status: 500,
                body: 'Internal Server Error',
            });
        });

        await page.goto('/actions');

        // Trigger a DAG
        await page.getByRole('button', { name: /trigger dag/i }).first().click();

        // Should show error toast
        await expect(page.getByText(/failed/i)).toBeVisible({ timeout: 5000 });
    });

    test('should link to Airflow dashboard', async ({ page }) => {
        await page.goto('/actions');

        const airflowLink = page.getByRole('link', { name: /airflow dashboard/i });
        await expect(airflowLink).toBeVisible();
    });
});

test.describe('Ops UI - Authentication', () => {
    test('should show sign in button when not authenticated', async ({ page }) => {
        await page.goto('/');

        // Should show sign in button in sidebar
        await expect(page.getByRole('button', { name: /sign in/i })).toBeVisible();
    });

    test('should show user info when authenticated', async ({ page }) => {
        await page.addInitScript(() => {
            (window as any).__NEXT_AUTH_SESSION = {
                user: {
                    email: 'ops@example.com',
                    name: 'Ops User',
                    tenantId: 'test-tenant',
                    roles: ['ops']
                },
                accessToken: 'mock-token',
            };
        });

        await page.goto('/');

        // Should show user email in sidebar
        await expect(page.getByText('ops@example.com')).toBeVisible();

        // Should show sign out button
        await expect(page.getByRole('button', { name: /sign out/i })).toBeVisible();
    });
});

import { NextRequest, NextResponse } from 'next/server';
import { auth } from '@/lib/auth';

export async function POST(request: NextRequest) {
    const session = await auth();

    if (!session?.accessToken) {
        return NextResponse.json(
            { error: 'Unauthorized' },
            { status: 401 }
        );
    }

    try {
        const body = await request.json();
        const { dag_id, conf } = body;

        if (!dag_id) {
            return NextResponse.json(
                { error: 'dag_id is required' },
                { status: 400 }
            );
        }

        const airflowUrl = process.env.AIRFLOW_URL || 'http://localhost:8080';
        const airflowAuth = process.env.AIRFLOW_AUTH || 'airflow:airflow';

        // Trigger DAG via Airflow REST API
        const response = await fetch(
            `${airflowUrl}/api/v1/dags/${dag_id}/dagRuns`,
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Basic ${Buffer.from(airflowAuth).toString('base64')}`,
                },
                body: JSON.stringify({
                    conf: conf || {},
                    note: `Triggered via Ops UI by ${session.user?.email}`,
                }),
            }
        );

        if (!response.ok) {
            const error = await response.text();
            console.error('Airflow API error:', error);
            return NextResponse.json(
                { error: 'Failed to trigger DAG', details: error },
                { status: response.status }
            );
        }

        const data = await response.json();

        return NextResponse.json(
            {
                message: 'DAG triggered successfully',
                dag_run_id: data.dag_run_id,
                execution_date: data.execution_date,
            },
            { status: 202 }
        );
    } catch (error) {
        console.error('Error triggering DAG:', error);
        return NextResponse.json(
            { error: 'Internal server error' },
            { status: 500 }
        );
    }
}

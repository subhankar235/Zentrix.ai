'use client';

import * as React from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ArrowLeft, TrendingDown, TrendingUp } from 'lucide-react';
import { PageHeader } from '@/components/page-header';
import {
  BanditPanel,
  CalibrationChart,
  ForecastCurveChart,
  MaeChart,
} from '@/components/forecasting/forecast-charts';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { StatusBadge } from '@/components/status-badge';
import { LoadingState, ErrorState } from '@/components/ui/state-feedback';
import { useForecastDetailQuery, useModelPerformanceQuery } from '@/hooks/use-forecasts';
import { useConnectionsQuery } from '@/hooks/use-connections';

export default function ForecastPage() {
  const params = useParams<{ connectionId: string }>();
  const { data: forecast, isLoading, isError, refetch } = useForecastDetailQuery(params.connectionId);
  const { data: perf } = useModelPerformanceQuery();
  const { data: connections = [] } = useConnectionsQuery();

  const conn = connections.find((c) => c.id === params.connectionId) || connections[0];

  if (isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader title="Forecast" />
        <LoadingState message="Computing degradation risk curves and bandit arm rewards..." />
      </div>
    );
  }

  if (isError || !forecast) {
    return (
      <div className="space-y-6">
        <PageHeader title="Forecast unavailable" />
        <ErrorState
          title="Could not load forecast"
          message="No active degradation forecast found for this database."
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  const risky = forecast.thresholdProbability >= 0.5;

  return (
    <div className="space-y-6">
      <PageHeader
        breadcrumb={
          <Link href="/dashboard" className="inline-flex items-center gap-1 hover:text-foreground">
            <ArrowLeft className="h-3 w-3" /> Dashboard
          </Link>
        }
        title={`Forecast — ${conn?.name || forecast.connectionId}`}
        description="Predictive degradation modeling with closed-loop learning. The system forecasts when today's healthy plan will stop being healthy."
      />

      <div
        className={
          risky
            ? 'flex flex-wrap items-center justify-between gap-3 rounded-lg border border-warning/40 bg-warning/10 p-4'
            : 'flex flex-wrap items-center justify-between gap-3 rounded-lg border border-success/30 bg-success/10 p-4'
        }
      >
        <div className="flex items-start gap-3">
          {risky ? (
            <TrendingUp className="mt-0.5 h-5 w-5 shrink-0 text-warning" />
          ) : (
            <TrendingDown className="mt-0.5 h-5 w-5 shrink-0 text-success" />
          )}
          <div>
            <p className={`text-sm font-semibold ${risky ? 'text-warning' : 'text-success'}`}>
              {forecast.headline}
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {risky
                ? 'Proactive action suggested before the degradation threshold is crossed.'
                : 'No proactive action required at this time.'}
            </p>
          </div>
        </div>
        {conn && <StatusBadge status={conn.health} dot />}
      </div>

      <Card>
        <CardHeader className="border-b [.border-b]:pb-3">
          <CardTitle>Degradation probability over the next 14 days</CardTitle>
          <CardDescription>
            Shaded band shows the prediction interval. Dashed line marks the risk threshold.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ForecastCurveChart curve={forecast.curve} thresholdDay={forecast.thresholdDay} />
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Model Calibration</CardTitle>
            <CardDescription>Predicted probability vs observed empirical frequency.</CardDescription>
          </CardHeader>
          <CardContent>
            <CalibrationChart buckets={perf?.calibration || forecast.calibration} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Mean Absolute Error (MAE) History</CardTitle>
            <CardDescription>Prediction error diminishing over iterations (closed-loop learning).</CardDescription>
          </CardHeader>
          <CardContent>
            <MaeChart points={perf?.mae || forecast.mae} />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>L3 Multi-Armed Bandit Strategy Selection</CardTitle>
          <CardDescription>Exploration / exploitation balance across optimization tactics.</CardDescription>
        </CardHeader>
        <CardContent>
          <BanditPanel arms={perf?.bandit || forecast.bandit} />
        </CardContent>
      </Card>
    </div>
  );
}

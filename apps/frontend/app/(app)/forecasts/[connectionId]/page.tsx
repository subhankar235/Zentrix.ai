'use client'

import * as React from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { ArrowLeft, FlaskConical, Lightbulb, TrendingDown, TrendingUp } from 'lucide-react'
import { PageHeader } from '@/components/page-header'
import {
  BanditPanel,
  CalibrationChart,
  ForecastCurveChart,
  MaeChart,
} from '@/components/forecasting/forecast-charts'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { StatusBadge } from '@/components/status-badge'
import { ConfidenceMeter } from '@/components/confidence-meter'
import { EmptyState, ErrorBanner } from '@/components/states'
import { Button } from '@/components/ui/button'
import { getConnection, getForecast } from '@/lib/mock-data'
import { recTypeLabel } from '@/lib/labels'

export default function ForecastPage() {
  const params = useParams<{ connectionId: string }>()
  const conn = getConnection(params.connectionId)
  const forecast = getForecast(params.connectionId)

  if (!forecast || !conn) {
    return (
      <div className="space-y-6">
        <PageHeader title="Forecast unavailable" />
        <EmptyState
          icon={TrendingUp}
          title="No forecast for this database"
          description="Forecasts appear once enough telemetry history has been collected."
          action={
            <Button asChild variant="outline" size="sm">
              <Link href="/dashboard">Back to dashboard</Link>
            </Button>
          }
        />
      </div>
    )
  }

  const risky = forecast.thresholdProbability >= 0.5

  return (
    <div className="space-y-6">
      <PageHeader
        breadcrumb={
          <Link href="/dashboard" className="inline-flex items-center gap-1 hover:text-foreground">
            <ArrowLeft className="h-3 w-3" /> Dashboard
          </Link>
        }
        title={`Forecast — ${conn.name}`}
        description="Predictive degradation modeling with closed-loop learning. The system forecasts when today's healthy plan will stop being healthy."
      />

      {/* Headline callout */}
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
                ? 'Proactive action suggested before the threshold is crossed.'
                : 'No proactive action required at this time.'}
            </p>
          </div>
        </div>
        <StatusBadge status={conn.health} dot />
      </div>

      {/* Degradation curve */}
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

      {/* Proactive suggestions */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold">Proactively suggested optimizations</h2>
        {forecast.suggestions.length === 0 ? (
          <EmptyState
            icon={Lightbulb}
            title="No proactive actions suggested"
            description="The bandit currently favors doing nothing on this workload — interventions would cost more than they save."
          />
        ) : (
          <div className="grid grid-cols-1 gap-3">
            {forecast.suggestions.map((rec) => (
              <Card key={rec.id} className="p-4">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                  <div className="min-w-0 space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <StatusBadge status={rec.type} label={recTypeLabel[rec.type]} tone="info" />
                      <StatusBadge status={rec.risk} label={`${rec.risk} risk`} />
                      <span className="text-sm font-medium">{rec.title}</span>
                    </div>
                    <p className="max-w-3xl text-sm text-muted-foreground text-pretty">
                      {rec.rationale}
                    </p>
                    <ConfidenceMeter value={100 - rec.uncertaintyPct} size="sm" />
                  </div>
                  <div className="flex items-center gap-4 lg:flex-col lg:items-end">
                    <p className="text-sm font-medium text-success">{rec.predictedImpact}</p>
                    <StatusBadge status="queued" label="Simulation queued" tone="neutral" />
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </section>

      {/* Learning quality */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader className="border-b [.border-b]:pb-3">
            <CardTitle>Calibration</CardTitle>
            <CardDescription>
              Predicted confidence vs. actual coverage. Bars close together mean the model knows what
              it does not know.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center gap-4 text-[11px] text-muted-foreground">
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-sm bg-[var(--chart-4)]" /> Predicted confidence
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-sm bg-[var(--chart-2)]" /> Actual coverage
              </span>
            </div>
            <CalibrationChart buckets={forecast.calibration} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="border-b [.border-b]:pb-3">
            <CardTitle>Prediction error across model versions</CardTitle>
            <CardDescription>
              Falling MAE is the proof that the forecasting loop is learning.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <MaeChart points={forecast.mae} />
          </CardContent>
        </Card>
      </div>

      {/* Bandit */}
      <Card>
        <CardHeader className="border-b [.border-b]:pb-3">
          <CardTitle>Strategy selector performance</CardTitle>
          <CardDescription>
            Which optimization type the bandit has learned works best for this workload, by average
            reward per pull.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <BanditPanel arms={forecast.bandit} />
        </CardContent>
      </Card>

      {!risky && forecast.suggestions.length === 0 ? (
        <ErrorBanner
          tone="warning"
          title="Cold start"
          description="This connection has limited history; forecasts will sharpen as telemetry accumulates."
        />
      ) : null}

      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <FlaskConical className="h-3.5 w-3.5" />
        Suggested optimizations follow the same simulate → verify → approve pipeline as diagnoses.
      </p>
    </div>
  )
}

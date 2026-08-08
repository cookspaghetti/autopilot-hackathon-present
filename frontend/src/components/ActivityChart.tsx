'use client'

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { motion } from 'framer-motion'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { CardWatermark } from '@/components/ui/card-watermark'
import { Icons } from '@/components/ui/icons'
import { cn } from '@/lib/utils'

// Static activity data — deterministic to avoid SSR hydration mismatch
const ACTIVITY_DATA = [
  { name: 'Mon', sessions: 315, success: 460, aiCalls: 210 },
  { name: 'Tue', sessions: 348, success: 485, aiCalls: 228 },
  { name: 'Wed', sessions: 390, success: 502, aiCalls: 245 },
  { name: 'Thu', sessions: 425, success: 498, aiCalls: 260 },
  { name: 'Fri', sessions: 460, success: 520, aiCalls: 275 },
  { name: 'Sat', sessions: 280, success: 440, aiCalls: 195 },
  { name: 'Sun', sessions: 310, success: 455, aiCalls: 208 },
]

// Custom tooltip component
function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean
  payload?: Array<{ name: string; value: number; color: string }>
  label?: string
}) {
  if (!active || !payload || !payload.length) return null

  return (
    <div className='rounded-xl border border-white/60 bg-white/95 p-3 shadow-float backdrop-blur-sm'>
      <p className='mb-2 text-xs font-medium text-brand-navy'>{label}</p>
      <div className='space-y-1'>
        {payload.map((entry, index) => (
          <div key={index} className='flex items-center gap-2 text-xs'>
            <div
              className='h-2 w-2 rounded-full'
              style={{ backgroundColor: entry.color }}
            />
            <span className='capitalize text-muted-foreground'>
              {entry.name}:
            </span>
            <span className='font-semibold text-brand-navy'>
              {entry.value.toLocaleString()}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

interface ActivityChartProps {
  className?: string
  title?: string
  description?: string
}

export function ActivityChart({
  className,
  title = 'Weekly Activity',
  description = 'AI interactions over the past 7 days',
}: ActivityChartProps) {
  const data = ACTIVITY_DATA

  // Calculate summary stats
  const totalSessions = data.reduce((acc, d) => acc + d.sessions, 0)
  const avgSuccess = Math.round(
    data.reduce((acc, d) => acc + d.success, 0) / data.length
  )
  const trend = (
    ((data[6].sessions - data[0].sessions) / data[0].sessions) *
    100
  ).toFixed(1)
  const isPositive = parseFloat(trend) >= 0

  return (
    <Card className={cn('relative overflow-hidden', className)}>
      <CardWatermark opacity={4} scale={1.2} />

      <CardHeader className='pb-2'>
        <div className='flex items-center justify-between'>
          <div>
            <CardTitle className='flex items-center gap-2'>
              <Icons.activity
                className='h-5 w-5 text-brand-cornflower'
                strokeWidth={1.5}
              />
              {title}
            </CardTitle>
            <p className='mt-1 text-sm text-muted-foreground'>{description}</p>
          </div>

          {/* Quick Stats */}
          <div className='hidden items-center gap-4 sm:flex'>
            <div className='text-right'>
              <p className='text-micro uppercase text-brand-muted'>
                Total Sessions
              </p>
              <p className='font-display text-lg font-bold text-brand-navy'>
                {totalSessions.toLocaleString()}
              </p>
            </div>
            <div className='h-10 w-px bg-border/50' />
            <div className='text-right'>
              <p className='text-micro uppercase text-brand-muted'>
                Avg Success
              </p>
              <p className='font-display text-lg font-bold text-brand-navy'>
                {avgSuccess.toLocaleString()}
              </p>
            </div>
            <motion.div
              className={cn(
                'flex items-center gap-1 rounded-full px-2 py-1 text-xs font-medium',
                isPositive
                  ? 'bg-emerald-50 text-emerald-600'
                  : 'bg-red-50 text-red-500'
              )}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.5 }}
            >
              {isPositive ? (
                <Icons.trendingUp className='h-3 w-3' strokeWidth={2} />
              ) : (
                <Icons.trendingUp
                  className='h-3 w-3 rotate-180'
                  strokeWidth={2}
                />
              )}
              {isPositive ? '+' : ''}
              {trend}%
            </motion.div>
          </div>
        </div>
      </CardHeader>

      <CardContent className='pt-0'>
        <div className='mt-4 h-[240px] w-full'>
          <ResponsiveContainer width='100%' height='100%'>
            <AreaChart
              data={data}
              margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
            >
              <defs>
                {/* Gradient for Sessions */}
                <linearGradient
                  id='gradientSessions'
                  x1='0'
                  y1='0'
                  x2='0'
                  y2='1'
                >
                  <stop offset='0%' stopColor='#5B8DEF' stopOpacity={0.4} />
                  <stop offset='95%' stopColor='#5B8DEF' stopOpacity={0} />
                </linearGradient>
                {/* Gradient for Success */}
                <linearGradient
                  id='gradientSuccess'
                  x1='0'
                  y1='0'
                  x2='0'
                  y2='1'
                >
                  <stop offset='0%' stopColor='#7C5CE7' stopOpacity={0.3} />
                  <stop offset='95%' stopColor='#7C5CE7' stopOpacity={0} />
                </linearGradient>
                {/* Gradient for AI Calls */}
                <linearGradient id='gradientAI' x1='0' y1='0' x2='0' y2='1'>
                  <stop offset='0%' stopColor='#141A42' stopOpacity={0.2} />
                  <stop offset='95%' stopColor='#141A42' stopOpacity={0} />
                </linearGradient>
              </defs>

              <CartesianGrid
                strokeDasharray='3 3'
                stroke='rgba(20, 26, 66, 0.06)'
                vertical={false}
              />

              <XAxis
                dataKey='name'
                axisLine={false}
                tickLine={false}
                tick={{
                  fill: '#7B8AB8',
                  fontSize: 11,
                  fontWeight: 500,
                }}
                dy={8}
              />

              <YAxis
                axisLine={false}
                tickLine={false}
                tick={{
                  fill: '#7B8AB8',
                  fontSize: 11,
                }}
                tickFormatter={(value) =>
                  value >= 1000 ? `${(value / 1000).toFixed(0)}k` : value
                }
              />

              <Tooltip content={<CustomTooltip />} />

              {/* AI Calls - Background layer */}
              <Area
                type='monotone'
                dataKey='aiCalls'
                name='AI Calls'
                stroke='#141A42'
                strokeWidth={1.5}
                fill='url(#gradientAI)'
                dot={false}
                activeDot={{
                  r: 4,
                  fill: '#141A42',
                  stroke: '#fff',
                  strokeWidth: 2,
                }}
              />

              {/* Success - Middle layer */}
              <Area
                type='monotone'
                dataKey='success'
                name='Success'
                stroke='#7C5CE7'
                strokeWidth={2}
                fill='url(#gradientSuccess)'
                dot={false}
                activeDot={{
                  r: 5,
                  fill: '#7C5CE7',
                  stroke: '#fff',
                  strokeWidth: 2,
                }}
              />

              {/* Sessions - Top layer */}
              <Area
                type='monotone'
                dataKey='sessions'
                name='Sessions'
                stroke='#5B8DEF'
                strokeWidth={2.5}
                fill='url(#gradientSessions)'
                dot={false}
                activeDot={{
                  r: 6,
                  fill: '#5B8DEF',
                  stroke: '#fff',
                  strokeWidth: 2,
                }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Legend */}
        <div className='mt-4 flex items-center justify-center gap-6 border-t border-border/30 pt-4'>
          <div className='flex items-center gap-2'>
            <div className='h-2 w-2 rounded-full bg-brand-cornflower' />
            <span className='text-xs text-muted-foreground'>Sessions</span>
          </div>
          <div className='flex items-center gap-2'>
            <div className='h-2 w-2 rounded-full bg-brand-purple' />
            <span className='text-xs text-muted-foreground'>Success</span>
          </div>
          <div className='flex items-center gap-2'>
            <div className='h-2 w-2 rounded-full bg-brand-navy' />
            <span className='text-xs text-muted-foreground'>AI Calls</span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}


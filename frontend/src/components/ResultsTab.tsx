import { useState, useEffect } from 'react'
import { fetchResults } from '../api'
import type { BenchmarkResult } from '../types'
import RecommendWidget from './RecommendWidget'
import Heatmap from './Heatmap'
import ResultsTable from './ResultsTable'

export default function ResultsTab() {
  const [results, setResults] = useState<BenchmarkResult[]>([])

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetchResults()
        setResults(res.results)
      } catch {
        // backend not ready
      }
    }
    load()
    const interval = setInterval(load, 10000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="results-tab">
      <RecommendWidget />
      <Heatmap />
      <ResultsTable results={results} />
    </div>
  )
}

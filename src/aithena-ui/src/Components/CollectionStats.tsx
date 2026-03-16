import { useStats, FacetEntry } from '../hooks/stats';

const TOP_AUTHORS = 20;

interface FacetTableProps {
  title: string;
  rows: FacetEntry[];
  limit?: number;
}

function FacetTable({ title, rows, limit }: FacetTableProps) {
  const displayed = limit ? rows.slice(0, limit) : rows;
  return (
    <div className="stats-table-block">
      <h3 className="stats-table-title">{title}</h3>
      {displayed.length === 0 ? (
        <p className="stats-empty">No data available.</p>
      ) : (
        <table className="stats-table">
          <thead>
            <tr>
              <th className="stats-th stats-th--value">Value</th>
              <th className="stats-th stats-th--count">Count</th>
            </tr>
          </thead>
          <tbody>
            {displayed.map((row) => (
              <tr key={row.value} className="stats-tr">
                <td className="stats-td stats-td--value">{row.value}</td>
                <td className="stats-td stats-td--count">{row.count.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function CollectionStats() {
  const { stats, loading, error } = useStats();

  if (loading) {
    return (
      <main className="stats-main">
        <p className="stats-loading">Loading statistics…</p>
      </main>
    );
  }

  if (error) {
    return (
      <main className="stats-main">
        <div className="search-error" role="alert">
          ⚠️ {error}
        </div>
      </main>
    );
  }

  if (!stats) {
    return null;
  }

  const { total_books, by_language, by_author, by_year, by_category, page_stats } = stats;

  return (
    <main className="stats-main">
      <header className="stats-header">
        <h2 className="stats-page-title">📊 Collection Stats</h2>
      </header>

      <section className="stats-summary-row">
        <div className="stats-big-number">
          <span className="stats-big-value">{total_books.toLocaleString()}</span>
          <span className="stats-big-label">Books indexed</span>
        </div>

        <div className="stats-page-summary">
          <h3 className="stats-table-title">Page stats</h3>
          <dl className="stats-dl">
            <div className="stats-dl-row">
              <dt className="stats-dt">Total pages</dt>
              <dd className="stats-dd">{page_stats.total.toLocaleString()}</dd>
            </div>
            <div className="stats-dl-row">
              <dt className="stats-dt">Average</dt>
              <dd className="stats-dd">{page_stats.avg.toLocaleString()}</dd>
            </div>
            <div className="stats-dl-row">
              <dt className="stats-dt">Min</dt>
              <dd className="stats-dd">{page_stats.min.toLocaleString()}</dd>
            </div>
            <div className="stats-dl-row">
              <dt className="stats-dt">Max</dt>
              <dd className="stats-dd">{page_stats.max.toLocaleString()}</dd>
            </div>
          </dl>
        </div>
      </section>

      <section className="stats-tables-grid">
        <FacetTable title="By Language" rows={by_language} />
        <FacetTable title={`By Author (top ${TOP_AUTHORS})`} rows={by_author} limit={TOP_AUTHORS} />
        <FacetTable title="By Year" rows={by_year} />
        <FacetTable title="By Category" rows={by_category} />
      </section>
    </main>
  );
}

export default CollectionStats;

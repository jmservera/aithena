import { useStats, StatsBucket, PageStats } from "../hooks/stats";

function StatTable({
  title,
  rows,
}: {
  title: string;
  rows: StatsBucket[];
}) {
  if (rows.length === 0) return null;
  return (
    <div className="stats-table-section">
      <h3 className="stats-section-title">{title}</h3>
      <table className="stats-table">
        <thead>
          <tr>
            <th className="stats-th stats-th--value">Value</th>
            <th className="stats-th stats-th--count">Books</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ value, count }) => (
            <tr key={value} className="stats-tr">
              <td className="stats-td stats-td--value">{value}</td>
              <td className="stats-td stats-td--count">
                {count.toLocaleString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PageStatsCard({ ps }: { ps: PageStats }) {
  return (
    <div className="stats-table-section">
      <h3 className="stats-section-title">Page Statistics</h3>
      <table className="stats-table">
        <tbody>
          <tr className="stats-tr">
            <td className="stats-td stats-td--value">Total pages</td>
            <td className="stats-td stats-td--count">
              {ps.total.toLocaleString()}
            </td>
          </tr>
          <tr className="stats-tr">
            <td className="stats-td stats-td--value">Average pages / book</td>
            <td className="stats-td stats-td--count">
              {ps.avg.toLocaleString()}
            </td>
          </tr>
          <tr className="stats-tr">
            <td className="stats-td stats-td--value">Min pages</td>
            <td className="stats-td stats-td--count">
              {ps.min.toLocaleString()}
            </td>
          </tr>
          <tr className="stats-tr">
            <td className="stats-td stats-td--value">Max pages</td>
            <td className="stats-td stats-td--count">
              {ps.max.toLocaleString()}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function CollectionStats() {
  const { data, loading, error } = useStats();

  if (loading) {
    return (
      <div className="stats-loading" role="status">
        Loading statistics…
      </div>
    );
  }

  if (error) {
    return (
      <div className="search-error" role="alert">
        ⚠️ {error}
      </div>
    );
  }

  if (!data) return null;

  const hasPageStats =
    data.page_stats && "total" in data.page_stats;

  return (
    <div className="stats-container">
      <div className="stats-hero">
        <span className="stats-hero-number">
          {data.total_books.toLocaleString()}
        </span>
        <span className="stats-hero-label">books indexed</span>
      </div>

      <div className="stats-grid">
        <StatTable title="By Language" rows={data.by_language} />
        <StatTable title="By Author (top 20)" rows={data.by_author} />
        <StatTable title="By Year" rows={data.by_year} />
        <StatTable title="By Category" rows={data.by_category} />
        {hasPageStats && (
          <PageStatsCard ps={data.page_stats as PageStats} />
        )}
      </div>
    </div>
  );
}

export default CollectionStats;

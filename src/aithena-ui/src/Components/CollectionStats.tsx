import { useIntl } from 'react-intl';

import { useStats, FacetEntry } from '../hooks/stats';

const TOP_AUTHORS = 20;

interface FacetTableProps {
  title: string;
  rows: FacetEntry[];
  limit?: number;
}

function FacetTable({ title, rows, limit }: FacetTableProps) {
  const intl = useIntl();
  const displayed = limit ? rows.slice(0, limit) : rows;
  return (
    <div className="stats-table-block">
      <h3 className="stats-table-title">{title}</h3>
      {displayed.length === 0 ? (
        <p className="stats-empty">{intl.formatMessage({ id: 'stats.noData' })}</p>
      ) : (
        <table className="stats-table">
          <thead>
            <tr>
              <th className="stats-th stats-th--value">
                {intl.formatMessage({ id: 'stats.tableValue' })}
              </th>
              <th className="stats-th stats-th--count">
                {intl.formatMessage({ id: 'stats.tableCount' })}
              </th>
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
  const intl = useIntl();
  const { stats, loading, error } = useStats();

  if (loading) {
    return (
      <main className="stats-main">
        <p className="stats-loading">{intl.formatMessage({ id: 'stats.loading' })}</p>
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
        <h2 className="stats-page-title">📊 {intl.formatMessage({ id: 'stats.title' })}</h2>
      </header>

      <section className="stats-summary-row">
        <div className="stats-big-number">
          <span className="stats-big-value">{total_books.toLocaleString()}</span>
          <span className="stats-big-label">
            {intl.formatMessage({ id: 'stats.booksIndexed' })}
          </span>
        </div>

        <div className="stats-page-summary">
          <h3 className="stats-table-title">{intl.formatMessage({ id: 'stats.pageStats' })}</h3>
          <dl className="stats-dl">
            <div className="stats-dl-row">
              <dt className="stats-dt">{intl.formatMessage({ id: 'stats.totalPages' })}</dt>
              <dd className="stats-dd">{page_stats.total.toLocaleString()}</dd>
            </div>
            <div className="stats-dl-row">
              <dt className="stats-dt">{intl.formatMessage({ id: 'stats.average' })}</dt>
              <dd className="stats-dd">{page_stats.avg.toLocaleString()}</dd>
            </div>
            <div className="stats-dl-row">
              <dt className="stats-dt">{intl.formatMessage({ id: 'stats.min' })}</dt>
              <dd className="stats-dd">{page_stats.min.toLocaleString()}</dd>
            </div>
            <div className="stats-dl-row">
              <dt className="stats-dt">{intl.formatMessage({ id: 'stats.max' })}</dt>
              <dd className="stats-dd">{page_stats.max.toLocaleString()}</dd>
            </div>
          </dl>
        </div>
      </section>

      <section className="stats-tables-grid">
        <FacetTable title={intl.formatMessage({ id: 'stats.byLanguage' })} rows={by_language} />
        <FacetTable
          title={intl.formatMessage({ id: 'stats.byAuthorTop' }, { count: TOP_AUTHORS })}
          rows={by_author}
          limit={TOP_AUTHORS}
        />
        <FacetTable title={intl.formatMessage({ id: 'stats.byYear' })} rows={by_year} />
        <FacetTable title={intl.formatMessage({ id: 'stats.byCategory' })} rows={by_category} />
      </section>
    </main>
  );
}

export default CollectionStats;

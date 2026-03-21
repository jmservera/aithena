import { useState, useMemo } from 'react';
import { useIntl, FormattedMessage } from 'react-intl';
import { useBackups, tierHealthColor, formatBytes, formatDuration } from '../hooks/backups';
import type {
  BackupTier,
  BackupStatus,
  BackupEntry,
  TierStatus,
  RestoreWizardStep,
  RestoreResult,
} from '../hooks/backups';
import './BackupDashboardPage.css';

function StatusBadge({ status }: { status: BackupStatus }) {
  const intl = useIntl();
  return (
    <span className={`status-badge ${status}`}>
      {intl.formatMessage({ id: `backup.status.${status}` })}
    </span>
  );
}

type SortKey = 'timestamp' | 'tier' | 'status' | 'size';
type SortDir = 'asc' | 'desc';

function TierStatusPanel({ tiers }: { tiers: TierStatus[] }) {
  const intl = useIntl();
  return (
    <section className="tier-status-section">
      <h3>
        <FormattedMessage id="backup.tierStatus.title" />
      </h3>
      <div
        className="tier-status-grid"
        role="list"
        aria-label={intl.formatMessage({ id: 'backup.tierStatus.aria' })}
      >
        {tiers.map((t) => (
          <div key={t.tier} className={`tier-card health-${tierHealthColor(t)}`} role="listitem">
            <h4>
              <FormattedMessage id={`backup.tier.${t.tier}`} />
            </h4>
            <dl>
              <dt>
                <FormattedMessage id="backup.tierStatus.lastBackup" />
              </dt>
              <dd>{t.last_backup ?? '\u2014'}</dd>
              <dt>
                <FormattedMessage id="backup.tierStatus.age" />
              </dt>
              <dd>
                {intl.formatMessage({ id: 'backup.tierStatus.ageValue' }, { hours: t.age_hours })}
              </dd>
              <dt>
                <FormattedMessage id="backup.tierStatus.rpo" />
              </dt>
              <dd>
                {intl.formatMessage({ id: 'backup.tierStatus.rpoValue' }, { hours: t.rpo_hours })}
              </dd>
              <dt>
                <FormattedMessage id="backup.tierStatus.size" />
              </dt>
              <dd>{formatBytes(t.size)}</dd>
            </dl>
          </div>
        ))}
      </div>
    </section>
  );
}

function BackupNowPanel({ onBackup }: { onBackup: (tier: BackupTier) => Promise<void> }) {
  const intl = useIntl();
  const [tier, setTier] = useState<BackupTier>('all');
  const [running, setRunning] = useState(false);

  const handleBackup = async () => {
    setRunning(true);
    try {
      await onBackup(tier);
    } finally {
      setRunning(false);
    }
  };

  return (
    <section className="backup-now-section">
      <h3>
        <FormattedMessage id="backup.backupNow.title" />
      </h3>
      <div className="backup-now-controls">
        <label htmlFor="backup-tier-select">
          <FormattedMessage id="backup.backupNow.tierLabel" />
        </label>
        <select
          id="backup-tier-select"
          value={tier}
          onChange={(e) => setTier(e.target.value as BackupTier)}
        >
          {(['all', 'critical', 'high', 'medium'] as BackupTier[]).map((t) => (
            <option key={t} value={t}>
              {intl.formatMessage({ id: `backup.tier.${t}` })}
            </option>
          ))}
        </select>
        <button
          className="backup-now-btn"
          onClick={handleBackup}
          disabled={running}
          aria-label={intl.formatMessage({ id: 'backup.backupNow.aria' })}
        >
          {running ? (
            <FormattedMessage id="backup.backupNow.running" />
          ) : (
            <FormattedMessage id="backup.backupNow.button" />
          )}
        </button>
      </div>
    </section>
  );
}

function BackupHistoryTable({
  backups,
  onRestore,
}: {
  backups: BackupEntry[];
  onRestore: (entry: BackupEntry) => void;
}) {
  const intl = useIntl();
  const [sortKey, setSortKey] = useState<SortKey>('timestamp');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const sorted = useMemo(() => {
    const copy = [...backups];
    copy.sort((a, b) => {
      let cmp = 0;
      if (sortKey === 'timestamp') cmp = a.timestamp.localeCompare(b.timestamp);
      else if (sortKey === 'tier') cmp = a.tier.localeCompare(b.tier);
      else if (sortKey === 'status') cmp = a.status.localeCompare(b.status);
      else if (sortKey === 'size') cmp = a.size - b.size;
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return copy;
  }, [backups, sortKey, sortDir]);

  const arrow = (key: SortKey) =>
    sortKey === key ? (sortDir === 'asc' ? ' \u25B2' : ' \u25BC') : '';

  return (
    <section className="backup-history-section">
      <h3>
        <FormattedMessage id="backup.history.title" />
      </h3>
      {backups.length === 0 ? (
        <p>
          <FormattedMessage id="backup.history.empty" />
        </p>
      ) : (
        <table
          className="backup-history-table"
          aria-label={intl.formatMessage({ id: 'backup.history.aria' })}
        >
          <thead>
            <tr>
              <th onClick={() => handleSort('timestamp')}>
                <FormattedMessage id="backup.history.headerTimestamp" />
                {arrow('timestamp')}
              </th>
              <th onClick={() => handleSort('tier')}>
                <FormattedMessage id="backup.history.headerTier" />
                {arrow('tier')}
              </th>
              <th onClick={() => handleSort('status')}>
                <FormattedMessage id="backup.history.headerStatus" />
                {arrow('status')}
              </th>
              <th onClick={() => handleSort('size')}>
                <FormattedMessage id="backup.history.headerSize" />
                {arrow('size')}
              </th>
              <th>
                <FormattedMessage id="backup.history.headerComponents" />
              </th>
              <th>
                <FormattedMessage id="backup.history.headerAction" />
              </th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((b) => (
              <tr key={b.id}>
                <td>{b.timestamp}</td>
                <td>
                  <FormattedMessage id={`backup.tier.${b.tier}`} />
                </td>
                <td>
                  <StatusBadge status={b.status} />
                </td>
                <td>{formatBytes(b.size)}</td>
                <td>{b.components.length}</td>
                <td>
                  {b.status === 'completed' && (
                    <button
                      className="restore-btn-small"
                      onClick={() => onRestore(b)}
                      aria-label={intl.formatMessage(
                        { id: 'backup.history.restoreLabel' },
                        { timestamp: b.timestamp }
                      )}
                    >
                      <FormattedMessage id="backup.history.restore" />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

const STEPS: RestoreWizardStep[] = ['select', 'preview', 'confirm', 'progress'];

function RestoreWizard({
  entry,
  onClose,
  onRestore,
  onTestRestore,
}: {
  entry: BackupEntry;
  onClose: () => void;
  onRestore: (req: { backup_id: string; components?: string[] }) => Promise<RestoreResult>;
  onTestRestore: (req: { backup_id: string; components?: string[] }) => Promise<RestoreResult>;
}) {
  const intl = useIntl();
  const [step, setStep] = useState<RestoreWizardStep>('select');
  const [result, setResult] = useState<RestoreResult | null>(null);
  const [busy, setBusy] = useState(false);

  const stepIndex = STEPS.indexOf(step);

  const goNext = () => {
    if (stepIndex < STEPS.length - 1) setStep(STEPS[stepIndex + 1]);
  };
  const goBack = () => {
    if (stepIndex > 0) setStep(STEPS[stepIndex - 1]);
  };

  const handleRestore = async () => {
    setBusy(true);
    try {
      const res = await onRestore({ backup_id: entry.id });
      setResult(res);
      setStep('progress');
    } catch (err) {
      setResult({
        status: 'failed',
        message: err instanceof Error ? err.message : 'Restore failed',
        components_restored: [],
        duration_seconds: 0,
      });
      setStep('progress');
    } finally {
      setBusy(false);
    }
  };

  const handleTest = async () => {
    setBusy(true);
    try {
      const res = await onTestRestore({ backup_id: entry.id });
      setResult(res);
      setStep('progress');
    } catch (err) {
      setResult({
        status: 'failed',
        message: err instanceof Error ? err.message : 'Test restore failed',
        components_restored: [],
        duration_seconds: 0,
      });
      setStep('progress');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="restore-overlay"
      role="presentation"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      onKeyDown={(e) => {
        if (e.key === 'Escape') onClose();
      }}
    >
      <div className="restore-wizard" role="dialog" aria-modal="true">
        <h3>
          <FormattedMessage id="backup.restore.title" />
        </h3>

        <nav
          className="restore-steps"
          aria-label={intl.formatMessage({ id: 'backup.restore.stepsAria' })}
        >
          {STEPS.map((s) => (
            <div key={s} className={`restore-step${s === step ? ' active' : ''}`}>
              <FormattedMessage
                id={`backup.restore.step${s.charAt(0).toUpperCase() + s.slice(1)}`}
              />
            </div>
          ))}
        </nav>

        {step === 'select' && (
          <div className="restore-info">
            <p>
              <FormattedMessage id="backup.restore.selectDescription" />
            </p>
            <dl>
              <dt>
                <FormattedMessage id="backup.restore.backupId" />
              </dt>
              <dd>{entry.id}</dd>
              <dt>
                <FormattedMessage id="backup.restore.backupTimestamp" />
              </dt>
              <dd>{entry.timestamp}</dd>
              <dt>
                <FormattedMessage id="backup.restore.backupTier" />
              </dt>
              <dd>
                <FormattedMessage id={`backup.tier.${entry.tier}`} />
              </dd>
            </dl>
          </div>
        )}

        {step === 'preview' && (
          <div className="restore-info">
            <p>
              <FormattedMessage id="backup.restore.previewDescription" />
            </p>
            <table className="restore-components-table">
              <thead>
                <tr>
                  <th>
                    <FormattedMessage id="backup.restore.componentName" />
                  </th>
                  <th>
                    <FormattedMessage id="backup.restore.componentSize" />
                  </th>
                  <th>
                    <FormattedMessage id="backup.restore.componentStatus" />
                  </th>
                </tr>
              </thead>
              <tbody>
                {entry.components.map((c) => (
                  <tr key={c.name}>
                    <td>{c.name}</td>
                    <td>{formatBytes(c.size)}</td>
                    <td>
                      <StatusBadge status={c.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {step === 'confirm' && (
          <div className="restore-info">
            <div className="restore-warning">
              <strong>
                <FormattedMessage id="backup.restore.warningTitle" />
              </strong>
              <p>
                <FormattedMessage id="backup.restore.warningOverwrite" />
              </p>
              <p>
                <FormattedMessage id="backup.restore.warningSafetyBackup" />
              </p>
            </div>
          </div>
        )}

        {step === 'progress' && (
          <div className="restore-result">
            {busy && (
              <p>
                <FormattedMessage id="backup.restore.inProgress" />
              </p>
            )}
            {result && (
              <>
                <StatusBadge status={result.status} />
                <p>{result.message}</p>
                <p>
                  <FormattedMessage
                    id="backup.restore.resultComponents"
                    values={{ count: result.components_restored.length }}
                  />
                </p>
                <p>
                  <FormattedMessage
                    id="backup.restore.resultDuration"
                    values={{
                      duration: formatDuration(result.duration_seconds),
                    }}
                  />
                </p>
              </>
            )}
          </div>
        )}

        <div className="restore-actions">
          {step !== 'progress' && (
            <button className="restore-cancel-btn" onClick={onClose}>
              <FormattedMessage id="backup.restore.cancel" />
            </button>
          )}
          {stepIndex > 0 && step !== 'progress' && (
            <button className="restore-back-btn" onClick={goBack}>
              <FormattedMessage id="backup.restore.back" />
            </button>
          )}
          {step === 'select' && (
            <button className="restore-next-btn" onClick={goNext}>
              <FormattedMessage id="backup.restore.next" />
            </button>
          )}
          {step === 'preview' && (
            <button className="restore-next-btn" onClick={goNext}>
              <FormattedMessage id="backup.restore.next" />
            </button>
          )}
          {step === 'confirm' && (
            <>
              <button className="restore-test-btn" onClick={handleTest} disabled={busy}>
                <FormattedMessage id="backup.restore.testRestore" />
              </button>
              <button className="restore-confirm-btn" onClick={handleRestore} disabled={busy}>
                <FormattedMessage id="backup.restore.confirmRestore" />
              </button>
            </>
          )}
          {step === 'progress' && !busy && (
            <button className="restore-done-btn" onClick={onClose}>
              {result ? (
                <FormattedMessage id="backup.restore.done" />
              ) : (
                <FormattedMessage id="backup.restore.close" />
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default function BackupDashboardPage() {
  const intl = useIntl();
  const {
    backups,
    tierStatuses,
    loading,
    error,
    refresh,
    triggerBackup,
    triggerRestore,
    testRestore,
  } = useBackups();
  const [restoreTarget, setRestoreTarget] = useState<BackupEntry | null>(null);

  return (
    <div className="backup-dashboard">
      <h2>
        <FormattedMessage id="backup.title" />
      </h2>

      {error && <div className="backup-error">{error}</div>}

      <button
        className="backup-refresh-btn"
        onClick={refresh}
        aria-label={intl.formatMessage({ id: 'backup.refresh' })}
      >
        <FormattedMessage id="backup.refresh" />
      </button>

      {loading ? (
        <p>
          <FormattedMessage id="backup.loading" />
        </p>
      ) : (
        <>
          <TierStatusPanel tiers={tierStatuses} />
          <BackupNowPanel onBackup={triggerBackup} />
          <BackupHistoryTable backups={backups} onRestore={setRestoreTarget} />
        </>
      )}

      {restoreTarget && (
        <RestoreWizard
          entry={restoreTarget}
          onClose={() => setRestoreTarget(null)}
          onRestore={triggerRestore}
          onTestRestore={testRestore}
        />
      )}
    </div>
  );
}

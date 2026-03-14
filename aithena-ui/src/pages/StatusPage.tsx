import IndexingStatus from "../Components/IndexingStatus";

function StatusPage() {
  return (
    <main className="status-main">
      <header className="status-header">
        <h2 className="status-title">🟢 Indexing Status</h2>
      </header>
      <div className="status-content">
        <IndexingStatus />
      </div>
    </main>
  );
}

export default StatusPage;

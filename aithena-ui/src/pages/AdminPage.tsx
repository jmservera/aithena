function AdminPage() {
  return (
    <div className="admin-page">
      <iframe
        src="/admin/streamlit/"
        title="Admin dashboard"
        className="admin-frame"
        sandbox="allow-same-origin allow-scripts allow-forms allow-popups"
      />
    </div>
  );
}

export default AdminPage;

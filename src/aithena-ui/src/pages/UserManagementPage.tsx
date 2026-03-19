import { FormEvent, useEffect, useState } from 'react';
import { useIntl } from 'react-intl';
import { useUsers, UserRecord, CreateUserPayload, UpdateUserPayload } from '../hooks/users';
import { useAuth } from '../contexts/AuthContext';

type ModalMode = 'add' | 'edit' | 'delete' | null;

function formatTimestamp(ts?: string): string {
  if (!ts) return '\u2014';
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

function UserManagementPage() {
  const intl = useIntl();
  const { user: currentUser } = useAuth();
  const { users, loading, error, fetchUsers, createUser, updateUser, deleteUser } = useUsers();
  const [modalMode, setModalMode] = useState<ModalMode>(null);
  const [selectedUser, setSelectedUser] = useState<UserRecord | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  // Add user form state
  const [newUsername, setNewUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newConfirmPassword, setNewConfirmPassword] = useState('');
  const [newRole, setNewRole] = useState('user');

  // Edit user form state
  const [editUsername, setEditUsername] = useState('');
  const [editRole, setEditRole] = useState('');

  useEffect(() => {
    void fetchUsers();
  }, [fetchUsers]);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(timer);
  }, [toast]);

  function openAddModal() {
    setNewUsername('');
    setNewPassword('');
    setNewConfirmPassword('');
    setNewRole('user');
    setFormError(null);
    setModalMode('add');
  }

  function openEditModal(user: UserRecord) {
    setSelectedUser(user);
    setEditUsername(user.username);
    setEditRole(user.role);
    setFormError(null);
    setModalMode('edit');
  }

  function openDeleteModal(user: UserRecord) {
    setSelectedUser(user);
    setFormError(null);
    setModalMode('delete');
  }

  function closeModal() {
    setModalMode(null);
    setSelectedUser(null);
    setFormError(null);
  }

  async function handleAddSubmit(e: FormEvent) {
    e.preventDefault();
    setFormError(null);

    if (!newUsername.trim()) return;

    if (newPassword !== newConfirmPassword) {
      setFormError(intl.formatMessage({ id: 'users.passwordMismatch' }));
      return;
    }
    if (newPassword.length < 10) {
      setFormError(intl.formatMessage({ id: 'users.passwordTooShort' }));
      return;
    }

    const payload: CreateUserPayload = {
      username: newUsername.trim(),
      password: newPassword,
      role: newRole,
    };

    setBusy(true);
    try {
      await createUser(payload);
      setToast(intl.formatMessage({ id: 'users.addSuccess' }));
      closeModal();
    } catch (err) {
      setFormError(
        err instanceof Error ? err.message : intl.formatMessage({ id: 'users.addFailed' })
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleEditSubmit(e: FormEvent) {
    e.preventDefault();
    if (!selectedUser) return;
    setFormError(null);

    const payload: UpdateUserPayload = {};
    if (editUsername.trim() !== selectedUser.username) payload.username = editUsername.trim();
    if (editRole !== selectedUser.role) payload.role = editRole;

    if (!payload.username && !payload.role) {
      closeModal();
      return;
    }

    setBusy(true);
    try {
      await updateUser(selectedUser.id, payload);
      setToast(intl.formatMessage({ id: 'users.editSuccess' }));
      closeModal();
    } catch (err) {
      setFormError(
        err instanceof Error ? err.message : intl.formatMessage({ id: 'users.editFailed' })
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteConfirm() {
    if (!selectedUser) return;
    setFormError(null);
    setBusy(true);
    try {
      await deleteUser(selectedUser.id);
      setToast(intl.formatMessage({ id: 'users.deleteSuccess' }));
      closeModal();
    } catch (err) {
      setFormError(
        err instanceof Error ? err.message : intl.formatMessage({ id: 'users.deleteFailed' })
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="admin-page">
      <header className="admin-header">
        <h2 className="admin-title">{intl.formatMessage({ id: 'users.title' })}</h2>
        <div className="admin-actions">
          <button type="button" className="admin-btn admin-btn--primary" onClick={openAddModal}>
            {intl.formatMessage({ id: 'users.addUser' })}
          </button>
          <button
            type="button"
            className="admin-btn"
            onClick={() => void fetchUsers()}
            disabled={loading}
          >
            {intl.formatMessage({ id: 'admin.refresh' })}
          </button>
        </div>
      </header>

      {toast && (
        <div className="users-toast" role="status">
          {toast}
        </div>
      )}

      {error && (
        <div className="admin-error-banner" role="alert">
          {error}
        </div>
      )}

      {loading && users.length === 0 && (
        <p className="admin-loading">{intl.formatMessage({ id: 'users.loading' })}</p>
      )}

      {users.length > 0 && (
        <div className="admin-table-wrapper">
          <table className="admin-table">
            <thead>
              <tr>
                <th>{intl.formatMessage({ id: 'users.headerUsername' })}</th>
                <th>{intl.formatMessage({ id: 'users.headerRole' })}</th>
                <th>{intl.formatMessage({ id: 'users.headerCreatedAt' })}</th>
                <th>{intl.formatMessage({ id: 'users.headerActions' })}</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>{u.username}</td>
                  <td>
                    <span className={`users-role-badge users-role-badge--${u.role}`}>{u.role}</span>
                  </td>
                  <td>{formatTimestamp(u.created_at)}</td>
                  <td>
                    <div className="users-action-btns">
                      <button type="button" className="admin-btn" onClick={() => openEditModal(u)}>
                        {intl.formatMessage({ id: 'users.edit' })}
                      </button>
                      <button
                        type="button"
                        className="admin-btn admin-btn--danger"
                        onClick={() => openDeleteModal(u)}
                        disabled={String(u.id) === String(currentUser?.id)}
                      >
                        {intl.formatMessage({ id: 'users.delete' })}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && users.length === 0 && !error && (
        <p className="admin-empty">{intl.formatMessage({ id: 'users.empty' })}</p>
      )}

      {/* Add User Modal */}
      {modalMode === 'add' && (
        <div className="users-modal-overlay" onClick={closeModal}>
          <div
            className="users-modal"
            role="dialog"
            aria-labelledby="add-user-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 id="add-user-title" className="users-modal-title">
              {intl.formatMessage({ id: 'users.addUser' })}
            </h3>
            <form onSubmit={handleAddSubmit} className="users-modal-form">
              <label className="login-label" htmlFor="add-username">
                {intl.formatMessage({ id: 'users.username' })}
              </label>
              <input
                id="add-username"
                className="login-input"
                type="text"
                value={newUsername}
                onChange={(e) => setNewUsername(e.target.value)}
                required
                autoComplete="off"
              />

              <label className="login-label" htmlFor="add-password">
                {intl.formatMessage({ id: 'users.password' })}
              </label>
              <input
                id="add-password"
                className="login-input"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={10}
                autoComplete="new-password"
              />

              <label className="login-label" htmlFor="add-confirm-password">
                {intl.formatMessage({ id: 'users.confirmPassword' })}
              </label>
              <input
                id="add-confirm-password"
                className="login-input"
                type="password"
                value={newConfirmPassword}
                onChange={(e) => setNewConfirmPassword(e.target.value)}
                required
                minLength={10}
                autoComplete="new-password"
              />

              <label className="login-label" htmlFor="add-role">
                {intl.formatMessage({ id: 'users.role' })}
              </label>
              <select
                id="add-role"
                className="login-input"
                value={newRole}
                onChange={(e) => setNewRole(e.target.value)}
              >
                <option value="viewer">{intl.formatMessage({ id: 'users.roleViewer' })}</option>
                <option value="user">{intl.formatMessage({ id: 'users.roleUser' })}</option>
                <option value="admin">{intl.formatMessage({ id: 'users.roleAdmin' })}</option>
              </select>

              {formError && (
                <div className="login-error" role="alert">
                  {formError}
                </div>
              )}

              <div className="users-modal-actions">
                <button
                  type="submit"
                  className="admin-btn admin-btn--primary"
                  disabled={busy || !newUsername.trim() || !newPassword}
                >
                  {busy
                    ? intl.formatMessage({ id: 'users.saving' })
                    : intl.formatMessage({ id: 'users.create' })}
                </button>
                <button type="button" className="admin-btn" onClick={closeModal} disabled={busy}>
                  {intl.formatMessage({ id: 'users.cancel' })}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit User Modal */}
      {modalMode === 'edit' && selectedUser && (
        <div className="users-modal-overlay" onClick={closeModal}>
          <div
            className="users-modal"
            role="dialog"
            aria-labelledby="edit-user-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 id="edit-user-title" className="users-modal-title">
              {intl.formatMessage({ id: 'users.editUser' })}
            </h3>
            <form onSubmit={handleEditSubmit} className="users-modal-form">
              <label className="login-label" htmlFor="edit-username">
                {intl.formatMessage({ id: 'users.username' })}
              </label>
              <input
                id="edit-username"
                className="login-input"
                type="text"
                value={editUsername}
                onChange={(e) => setEditUsername(e.target.value)}
                required
                autoComplete="off"
              />

              <label className="login-label" htmlFor="edit-role">
                {intl.formatMessage({ id: 'users.role' })}
              </label>
              <select
                id="edit-role"
                className="login-input"
                value={editRole}
                onChange={(e) => setEditRole(e.target.value)}
              >
                <option value="viewer">{intl.formatMessage({ id: 'users.roleViewer' })}</option>
                <option value="user">{intl.formatMessage({ id: 'users.roleUser' })}</option>
                <option value="admin">{intl.formatMessage({ id: 'users.roleAdmin' })}</option>
              </select>

              {formError && (
                <div className="login-error" role="alert">
                  {formError}
                </div>
              )}

              <div className="users-modal-actions">
                <button type="submit" className="admin-btn admin-btn--primary" disabled={busy}>
                  {busy
                    ? intl.formatMessage({ id: 'users.saving' })
                    : intl.formatMessage({ id: 'users.save' })}
                </button>
                <button type="button" className="admin-btn" onClick={closeModal} disabled={busy}>
                  {intl.formatMessage({ id: 'users.cancel' })}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {modalMode === 'delete' && selectedUser && (
        <div className="users-modal-overlay" onClick={closeModal}>
          <div
            className="users-modal"
            role="dialog"
            aria-labelledby="delete-user-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 id="delete-user-title" className="users-modal-title">
              {intl.formatMessage({ id: 'users.deleteUser' })}
            </h3>
            <p className="users-modal-body">
              {intl.formatMessage(
                { id: 'users.deleteConfirm' },
                { username: selectedUser.username }
              )}
            </p>

            {formError && (
              <div className="login-error" role="alert">
                {formError}
              </div>
            )}

            <div className="users-modal-actions">
              <button
                type="button"
                className="admin-btn admin-btn--danger"
                onClick={handleDeleteConfirm}
                disabled={busy}
              >
                {busy
                  ? intl.formatMessage({ id: 'users.deleting' })
                  : intl.formatMessage({ id: 'users.delete' })}
              </button>
              <button type="button" className="admin-btn" onClick={closeModal} disabled={busy}>
                {intl.formatMessage({ id: 'users.cancel' })}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

export default UserManagementPage;

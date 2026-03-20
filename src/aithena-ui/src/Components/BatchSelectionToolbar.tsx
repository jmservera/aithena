import { FormattedMessage } from 'react-intl';

import './BatchEditPanel.css';

interface BatchSelectionToolbarProps {
  selectedCount: number;
  onEdit: () => void;
  onClearSelection: () => void;
}

function BatchSelectionToolbar({
  selectedCount,
  onEdit,
  onClearSelection,
}: BatchSelectionToolbarProps) {
  if (selectedCount === 0) return null;

  return (
    <div className="batch-toolbar" role="toolbar" aria-label="Batch selection actions">
      <span className="batch-toolbar-count">
        <FormattedMessage id="batchEdit.selectedCount" values={{ count: selectedCount }} />
      </span>
      <button type="button" className="batch-toolbar-edit-btn" onClick={onEdit}>
        <FormattedMessage id="batchEdit.editSelected" values={{ count: selectedCount }} />
      </button>
      <button type="button" className="batch-toolbar-clear-btn" onClick={onClearSelection}>
        <FormattedMessage id="batchEdit.clearSelection" />
      </button>
    </div>
  );
}

export default BatchSelectionToolbar;

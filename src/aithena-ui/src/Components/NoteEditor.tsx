import { useCallback, useRef, useState } from 'react';
import { useIntl } from 'react-intl';

const NOTE_MAX_LENGTH = 5000;

interface NoteEditorProps {
  itemId: string;
  collectionId: string;
  initialNote: string;
  onSave: (itemId: string, note: string) => void;
  saving?: boolean;
}

function NoteEditor({ itemId, initialNote, onSave, saving }: NoteEditorProps) {
  const intl = useIntl();
  const [note, setNote] = useState(initialNote);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const value = e.target.value.slice(0, NOTE_MAX_LENGTH);
      setNote(value);
      onSave(itemId, value);
    },
    [itemId, onSave]
  );

  return (
    <div className="note-editor">
      <label className="note-editor-label" htmlFor={`note-${itemId}`}>
        {intl.formatMessage({ id: 'collections.noteLabel' })}
      </label>
      <textarea
        ref={textareaRef}
        id={`note-${itemId}`}
        className="note-editor-textarea"
        value={note}
        onChange={handleChange}
        maxLength={NOTE_MAX_LENGTH}
        placeholder={intl.formatMessage({ id: 'collections.notePlaceholder' })}
        rows={2}
        aria-label={intl.formatMessage({ id: 'collections.noteLabel' })}
      />
      <div className="note-editor-footer">
        <span className="note-editor-count">
          {note.length}/{NOTE_MAX_LENGTH}
        </span>
        {saving && (
          <span className="note-editor-saving" aria-live="polite">
            {intl.formatMessage({ id: 'collections.noteSaving' })}
          </span>
        )}
      </div>
    </div>
  );
}

export default NoteEditor;

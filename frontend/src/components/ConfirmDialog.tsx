interface Props {
  title: string;
  message: string;
  confirmLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({ title, message, confirmLabel = "Confirm", danger, onConfirm, onCancel }: Props) {
  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" onClick={onCancel}>
      <div className="card max-w-sm w-full" onClick={(e) => e.stopPropagation()}>
        <div className="font-medium text-base mb-2">{title}</div>
        <div className="text-sm text-muted mb-4">{message}</div>
        <div className="flex justify-end gap-2">
          <button className="btn-ghost text-sm" onClick={onCancel}>Cancel</button>
          <button
            className={"btn text-sm " + (danger ? "!bg-red-500 hover:!bg-red-600" : "")}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

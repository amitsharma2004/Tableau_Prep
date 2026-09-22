export function DataTable({ rows }: { rows: Record<string, unknown>[] | null | undefined }) {
  if (!rows || rows.length === 0) {
    return <p className="text-sm text-slate-500 italic">No rows.</p>;
  }
  const columns = Object.keys(rows[0]);

  return (
    <div className="overflow-x-auto border border-slate-200 rounded">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-50">
          <tr>
            {columns.map((col) => (
              <th key={col} className="text-left font-medium text-slate-600 px-3 py-2 whitespace-nowrap">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row, i) => (
            <tr key={i}>
              {columns.map((col) => (
                <td key={col} className="px-3 py-2 whitespace-nowrap text-slate-800">
                  {row[col] === null || row[col] === undefined ? (
                    <span className="text-slate-400 italic">null</span>
                  ) : (
                    String(row[col])
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

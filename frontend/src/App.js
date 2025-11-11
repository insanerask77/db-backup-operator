import React, { useState, useEffect } from 'react';

function App() {
  const [backups, setBackups] = useState([]);
  const [history, setHistory] = useState({});

  useEffect(() => {
    fetch('/api/backups')
      .then(res => res.json())
      .then(data => setBackups(data));
  }, []);

  const fetchHistory = (name) => {
    fetch(`/api/backups/history/${name}`)
      .then(res => res.json())
      .then(data => setHistory(prev => ({ ...prev, [name]: data })));
  };

  const runBackup = (name) => {
    fetch(`/api/backups/run/${name}`, { method: 'POST' });
  };

  const restoreBackup = (name) => {
    fetch(`/api/backups/restore/${name}`, { method: 'POST' });
  };

  return (
    <div className="container mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">Backup Dashboard</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {backups.map(backup => (
          <div key={backup.name} className="border p-4 rounded-lg">
            <h2 className="text-xl font-semibold">{backup.name}</h2>
            <p><strong>Type:</strong> {backup.type}</p>
            <p><strong>Schedule:</strong> {backup.schedule}</p>
            <div className="flex space-x-2 mt-4">
              <button onClick={() => runBackup(backup.name)} className="bg-blue-500 text-white px-4 py-2 rounded">Backup Now</button>
              <button onClick={() => restoreBackup(backup.name)} className="bg-green-500 text-white px-4 py-2 rounded">Restore</button>
              <button onClick={() => fetchHistory(backup.name)} className="bg-gray-500 text-white px-4 py-2 rounded">View History</button>
            </div>
            {history[backup.name] && (
              <div className="mt-4">
                <h3 className="text-lg font-semibold">History</h3>
                <ul>
                  {history[backup.name].map((h, i) => (
                    <li key={i} className="text-sm">
                      {h.timestamp}: {h.status} ({h.duration.toFixed(2)}s, {(h.size / 1024).toFixed(2)} KB)
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default App;

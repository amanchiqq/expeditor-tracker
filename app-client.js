const API_BASE = window.TRACKER_CONFIG.apiBase.replace(/\/$/, '');

function localDateTime(value) {
  if (!value) return '';
  const date = new Date(value);
  const pad = value => String(value).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function appendTaskRow(tbody, task, editTask, deleteTask) {
  const row = document.createElement('tr');
  row.className = 'border-t';
  for (const value of [task.id, task.description ?? 'N/A', task.status, task.created_at, task.eta ?? 'N/A']) {
    const cell = document.createElement('td');
    cell.className = 'px-4 py-2';
    cell.textContent = String(value);
    row.appendChild(cell);
  }
  const actions = document.createElement('td');
  for (const [text, callback] of [['Edit', editTask], ['Delete', deleteTask]]) {
    const button = document.createElement('button');
    button.textContent = text;
    button.className = 'p-2 border rounded mr-1';
    button.addEventListener('click', () => callback(task.id));
    actions.appendChild(button);
  }
  row.appendChild(actions);
  tbody.appendChild(row);
}

async function trackerFetch(url, options) {
  const response = await fetch(url, options);
  if (url.startsWith(API_BASE + '/') && response.status === 401) {
    localStorage.removeItem('token');
    window.location.href = 'login.html';
    throw new Error('Session expired. Please sign in again.');
  }
  return response;
}

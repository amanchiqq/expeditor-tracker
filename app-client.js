const API_BASE = window.TRACKER_CONFIG.apiBase.replace(/\/$/, '');

function localDateTime(value) {
  if (!value) return '';
  const date = new Date(value);
  const pad = value => String(value).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}.${String(date.getMilliseconds()).padStart(3, '0')}`;
}

function formatTaskTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat('ru-RU', {dateStyle:'short',timeStyle:'short'}).format(date);
}

function taskListUrl({page, perPage, taskId, expeditorId, status, date}) {
  const params=new URLSearchParams({page:String(page),per_page:String(perPage)});
  for (const [key,value] of [['task_id',taskId],['expeditor_id',expeditorId],['status',status],['date',date]]) {
    if (value !== '' && value !== null && value !== undefined) params.set(key,String(value));
  }
  return `${API_BASE}/tasks?${params}`;
}

function appendTaskRow(tbody, task, editTask, deleteTask) {
  const row = document.createElement('tr');
  row.className = 'border-t';
  for (const value of [task.id, task.description ?? 'N/A', ({in_progress:'В работе',completed:'Завершено'}[task.status] || task.status), formatTaskTime(task.created_at), formatTaskTime(task.eta)]) {
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

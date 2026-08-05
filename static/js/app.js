function app() {
  const base = {
    token: localStorage.getItem('plan365_token') || null,
    user: null,
    authMode: 'login',
    authLoading: false,
    authError: '',
    loginForm: { username: '', password: '' },
    regForm: { username: '', email: '', password: '', full_name: '' },
    theme: localStorage.getItem('plan365_theme') || 'system',
    view: 'overview',
    subView: 'list',
    projects: [],
    tasks: [],
    users: [],
    currentProject: null,
    filterType: '',
    filterStatus: '',
    filterPriority: '',
    types: ['2D CAD', 'CAD', 'CAM', 'Tools', 'Others'],
    statuses: ['Todo', 'In Progress', 'Review', 'Testing', 'Done', 'Blocked', 'Handoff'],
    priorities: ['High', 'Medium', 'Low'],
    calYear: new Date().getFullYear(),
    calMonth: new Date().getMonth(), // 0-based
    ganttViewMode: 'Week',
    ganttInstance: null,
    ganttCollapsed: {},
    ganttFilterType: '',
    ganttFilterStatus: '',
    ganttFilterAssignee: '',
    ganttFilterBlocked: false,
    ganttShowCritical: false,
    depLagDays: 0,
    kanbanSortables: [],
    detailTask: null,
    detailForm: {},
    detailDeps: { predecessors: [], successors: [], blocked: false, predecessor_ids: [], successor_ids: [] },
    depPickId: '',
    settings: {},
    pref: { default_view: 'list' },
    aiPreview: '',
    editingId: null,
    editForm: {},
    newTask: { title: '', type: 'Others', status: 'Todo', priority: 'Medium', due_date: '', project_id: '' },
    showNewProject: false,
    newProject: { name: '', description: '', color: '#3b82f6' },
    toast: '',
    canEdit: true,

    async init() {
      this.applyTheme();
      if (this.token) {
        try {
          this.user = await this.api('/api/auth/me');
          await this.loadProjects();
          await this.loadTasks();
          await this.loadUsers();
          await this.loadSettings();
          await this.loadPrefs();
        } catch (e) {
          this.logout();
        }
      }
    },

    applyTheme() {
      const root = document.documentElement;
      if (this.theme === 'dark' || (this.theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
        root.classList.add('dark');
      } else {
        root.classList.remove('dark');
      }
      localStorage.setItem('plan365_theme', this.theme);
    },
    toggleTheme() {
      this.theme = document.documentElement.classList.contains('dark') ? 'light' : 'dark';
      this.applyTheme();
    },

    async api(path, opts = {}) {
      const headers = opts.headers || {};
      if (this.token) headers['Authorization'] = 'Bearer ' + this.token;
      if (opts.body && typeof opts.body === 'object' && !(opts.body instanceof FormData)) {
        headers['Content-Type'] = 'application/json';
        opts.body = JSON.stringify(opts.body);
      }
      const res = await fetch(path, { ...opts, headers });
      if (res.status === 401) { this.logout(); throw new Error('Unauthorized'); }
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        let detail = err.detail || res.statusText;
        if (detail && typeof detail === 'object') {
          if (detail.message) {
            detail = detail.message + (detail.cycle_path ? ' [' + detail.cycle_path.join(' → ') + ']' : '');
          } else {
            detail = JSON.stringify(detail);
          }
        }
        throw new Error(detail);
      }
      if (res.status === 204) return null;
      return res.json();
    },

    async login() {
      this.authLoading = true; this.authError = '';
      try {
        const body = new URLSearchParams();
        body.append('username', this.loginForm.username);
        body.append('password', this.loginForm.password);
        const res = await fetch('/api/auth/login', { method: 'POST', body, headers: { 'Content-Type': 'application/x-www-form-urlencoded' } });
        if (!res.ok) throw new Error('Login gagal');
        const data = await res.json();
        this.token = data.access_token;
        localStorage.setItem('plan365_token', this.token);
        this.user = await this.api('/api/auth/me');
        await this.loadProjects();
        await this.loadTasks();
        await this.loadUsers();
      } catch (e) {
        this.authError = e.message || 'Login gagal';
      } finally {
        this.authLoading = false;
      }
    },

    async register() {
      this.authLoading = true; this.authError = '';
      try {
        await this.api('/api/auth/register', { method: 'POST', body: this.regForm });
        this.authMode = 'login';
        this.loginForm.username = this.regForm.username;
        this.showToast('Registrasi berhasil. Silakan login.');
      } catch (e) {
        this.authError = e.message;
      } finally {
        this.authLoading = false;
      }
    },

    logout() {
      this.token = null;
      this.user = null;
      localStorage.removeItem('plan365_token');
    },

    async loadProjects() {
      this.projects = await this.api('/api/projects');
    },
    async loadUsers() {
      this.users = await this.api('/api/users');
    },
    async loadTasks() {
      let q = [];
      if (this.currentProject) q.push('project_id=' + this.currentProject.id);
      if (this.filterType) q.push('type=' + encodeURIComponent(this.filterType));
      if (this.filterStatus) q.push('status=' + encodeURIComponent(this.filterStatus));
      if (this.filterPriority) q.push('priority=' + encodeURIComponent(this.filterPriority));
      const qs = q.length ? '?' + q.join('&') : '';
      this.tasks = await this.api('/api/tasks' + qs);
    },

    selectProject(p) {
      this.currentProject = p;
      this.view = 'project';
      this.newTask.project_id = p.id;
      this.loadTasks();
    },

    startEdit(task) {
      this.editingId = task.id;
      this.editForm = {
        title: task.title,
        type: task.type,
        status: task.status,
        priority: task.priority,
        due_date: task.due_date || ''
      };
    },

    async saveEdit(task) {
      try {
        if ((this.editForm.status === 'Done' || this.editForm.status === 'Handoff') && this.isTaskBlocked(task)) {
          this.showToast('Blocked: selesaikan predecessor dulu');
          return;
        }
        const updated = await this.api('/api/tasks/' + task.id, { method: 'PUT', body: this.editForm });
        const idx = this.tasks.findIndex(t => t.id === task.id);
        if (idx >= 0) this.tasks[idx] = { ...this.tasks[idx], ...updated };
        this.editingId = null;
        this.showToast('Task updated');
      } catch (e) {
        this.showToast(e.message);
      }
    },

    async createTask() {
      if (!this.newTask.title.trim()) return;
      const payload = { ...this.newTask };
      if (this.currentProject) payload.project_id = this.currentProject.id;
      if (!payload.project_id) {
        this.showToast('Pilih project terlebih dahulu');
        return;
      }
      payload.project_id = parseInt(payload.project_id);
      try {
        const t = await this.api('/api/tasks', { method: 'POST', body: payload });
        this.tasks.unshift(t);
        this.newTask = { title: '', type: 'Others', status: 'Todo', priority: 'Medium', due_date: '', project_id: this.currentProject?.id || '' };
        this.showToast('Task created');
        this.loadProjects();
      } catch (e) {
        this.showToast(e.message);
      }
    },

    async deleteTask(task) {
      if (!confirm('Hapus task "' + task.title + '"?')) return;
      try {
        await this.api('/api/tasks/' + task.id, { method: 'DELETE' });
        this.tasks = this.tasks.filter(t => t.id !== task.id);
        this.showToast('Task deleted');
        this.loadProjects();
      } catch (e) {
        this.showToast(e.message);
      }
    },

    async createProject() {
      if (!this.newProject.name.trim()) return;
      try {
        const p = await this.api('/api/projects', { method: 'POST', body: this.newProject });
        this.projects.push(p);
        this.showNewProject = false;
        this.newProject = { name: '', description: '', color: '#3b82f6' };
        this.selectProject(p);
        this.showToast('Project created');
      } catch (e) {
        this.showToast(e.message);
      }
    },

    typeClass(t) {
      const map = {
        '2D CAD': 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
        'CAD': 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300',
        'CAM': 'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300',
        'Tools': 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
        'Others': 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'
      };
      return map[t] || map['Others'];
    },
    statusClass(s) {
      const map = {
        'Todo': 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300',
        'In Progress': 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
        'Review': 'bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300',
        'Testing': 'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-300',
        'Done': 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300',
        'Blocked': 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
        'Handoff': 'bg-pink-100 text-pink-700 dark:bg-pink-900/40 dark:text-pink-300'
      };
      return map[s] || map['Todo'];
    },
    priorityClass(p) {
      const map = {
        'High': 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
        'Medium': 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300',
        'Low': 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300'
      };
      return map[p] || map['Medium'];
    },

    // ---- Calendar ----
    get calMonthLabel() {
      const names = ['January','February','March','April','May','June','July','August','September','October','November','December'];
      return names[this.calMonth] + ' ' + this.calYear;
    },
    get calDays() {
      const year = this.calYear, month = this.calMonth;
      const first = new Date(year, month, 1);
      const last = new Date(year, month + 1, 0);
      // Monday-start: getDay() 0=Sun → convert
      let startPad = (first.getDay() + 6) % 7;
      const days = [];
      const todayStr = new Date().toISOString().slice(0, 10);
      // previous month padding
      const prevLast = new Date(year, month, 0).getDate();
      for (let i = startPad - 1; i >= 0; i--) {
        const d = prevLast - i;
        const dt = new Date(year, month - 1, d);
        days.push(this._calDay(dt, false, todayStr));
      }
      for (let d = 1; d <= last.getDate(); d++) {
        const dt = new Date(year, month, d);
        days.push(this._calDay(dt, true, todayStr));
      }
      // next month padding to fill 6 rows (42 cells)
      let next = 1;
      while (days.length < 42) {
        const dt = new Date(year, month + 1, next++);
        days.push(this._calDay(dt, false, todayStr));
      }
      return days;
    },
    _calDay(dt, isCurrentMonth, todayStr) {
      const iso = dt.toISOString().slice(0, 10);
      const dayTasks = this.tasks.filter(t => t.due_date === iso || t.start_date === iso);
      return {
        date: dt.getDate(),
        iso,
        isCurrentMonth,
        isToday: iso === todayStr,
        tasks: dayTasks.slice(0, 4)
      };
    },
    calPrev() {
      if (this.calMonth === 0) { this.calMonth = 11; this.calYear--; }
      else this.calMonth--;
    },
    calNext() {
      if (this.calMonth === 11) { this.calMonth = 0; this.calYear++; }
      else this.calMonth++;
    },

    // ---- Settings / Prefs ----
    async loadSettings() {
      try { this.settings = await this.api('/api/settings'); } catch(e) {}
    },
    async loadPrefs() {
      try {
        this.pref = await this.api('/api/settings/preferences');
        if (this.pref.theme) { this.theme = this.pref.theme; this.applyTheme(); }
      } catch(e) {}
    },
    async savePrefs() {
      try {
        await this.api('/api/settings/preferences', { method: 'PUT', body: this.pref });
        this.showToast('Preferences saved');
      } catch(e) { this.showToast(e.message); }
    },
    async testAiSync() {
      try {
        const data = await this.api('/api/ai/sync');
        this.aiPreview = JSON.stringify(data, null, 2);
      } catch(e) { this.showToast(e.message); }
    },

    // ---- Export / Backup ----
    async exportCsv() {
      try {
        const q = [];
        if (this.currentProject) q.push('project_id=' + this.currentProject.id);
        const path = '/api/export/tasks.csv' + (q.length ? '?' + q.join('&') : '');
        const res = await fetch(path, { headers: { Authorization: 'Bearer ' + this.token } });
        if (!res.ok) throw new Error('Export gagal');
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'plan365-tasks.csv';
        a.click();
        URL.revokeObjectURL(url);
        this.showToast('CSV diunduh');
      } catch (e) {
        this.showToast(e.message);
      }
    },
    async downloadBackup() {
      try {
        const res = await fetch('/api/backup', { headers: { Authorization: 'Bearer ' + this.token } });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || 'Backup gagal');
        }
        const blob = await res.blob();
        const cd = res.headers.get('Content-Disposition') || '';
        const m = cd.match(/filename="?([^"]+)"?/);
        const name = m ? m[1] : 'plan365-backup.db';
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = name;
        a.click();
        URL.revokeObjectURL(url);
        this.showToast('Backup DB diunduh');
      } catch (e) {
        this.showToast(e.message);
      }
    },

    showToast(msg) {
      this.toast = msg;
      setTimeout(() => this.toast = '', 3500);
    },

    // mixins attached below via Object.assign in app()
  };

  // Preserve getters (ganttGroups, etc.) from mixins
  for (const m of [window.Plan365Gantt, window.Plan365Deps, window.Plan365Kanban]) {
    if (!m) continue;
    Object.defineProperties(base, Object.getOwnPropertyDescriptors(m));
  }
  return base;
}

function app() {
  const base = {
    token: localStorage.getItem('plan365_token') || null,
    user: null,
    authMode: 'login',
    authLoading: false,
    authError: '',
    loginForm: { username: '', password: '' },
    regForm: { username: '', email: '', password: '', full_name: '' },
    theme: (localStorage.getItem('plan365_theme') === 'dark' ? 'dark' : 'dark'),
    view: 'dashboard',
    subView: 'list',
    projects: [],
    tasks: [],
    users: [],
    currentProject: null,
    filterTypes: [],
    filterStatuses: [],
    filterPriorities: [],
    templatesOpen: true,
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
    searchQuery: '',
    showNewTask: false,
    sidebarCollapsed: localStorage.getItem('plan365_sidebar') === '1',
    ganttListCollapsed: false,
    projectFilterStatus: 'Active', // sidebar: Active | '' all | Archived
    showArchivedProjects: false,
    workload: { assignees: [], milestones_upcoming: [] },
    cascadeSchedule: localStorage.getItem('plan365_cascade') !== '0',
    showWorkload: false,
    dashboard: null,
    projectTemplates: [],
    templateEdit: [],
    templateEditJson: '',
    templateEditMode: 'list', // list | json
    dashLoading: false,
    rtConnected: false,
    rtStatus: 'off',
    _es: null,
    _rtDebounce: null,
    settingsEdit: { task_types: '', priorities: '', statuses: '', default_type: '', default_priority: '', default_status: '' },
    showNewUser: false,
    newUser: { username: '', email: '', password: '', full_name: '', role: 'user' },

    depLagDays: 0,
    kanbanSortables: [],
    detailTask: null,
    detailForm: {},
    detailDeps: { predecessors: [], successors: [], blocked: false, predecessor_ids: [], successor_ids: [] },
    depPickId: '',
    settings: {},
    pref: { default_view: 'list' },
    aiPreview: '',
    aiAnalysis: null,
    aiLoading: false,
    aiChatInput: '',
    aiChatReply: '',
    aiChatLog: [],
    aiSettings: { ai_enabled: false, ai_api_url: '', ai_model: '', ai_system_prompt: '', ai_api_key_set: false, ai_api_key_masked: '' },
    aiSettingsForm: { ai_enabled: false, ai_api_url: '', ai_model: '', ai_system_prompt: '', ai_api_key: '' },

    editingId: null,
    editForm: {},
    newTask: { title: '', type: 'Others', status: 'Todo', priority: 'Medium', due_date: '', project_id: '' },
    showNewProject: false,
    newProjectStep: 1,
    draftTemplateTasks: [],
    newProject: { name: '', description: '', color: '#3b82f6', status: 'Active', start_date: '', due_date: '' , template_id: '' },
    showEditProject: false,
    editProject: {},
    projectStatuses: ['Active', 'On Hold', 'Completed', 'Archived'],
    toast: '',
    canEdit: true,

    async init() {
      this.applyTheme();
      if (this.token) {
        try {
          this.user = await this.api('/api/auth/me');
          await this.loadProjects();
          await this.loadTasks();
          await this.loadDashboard();
          await this.loadUsers();
          this.connectRealtime();
          await this.loadTemplates();
          await this.loadSettings();
          await this.loadPrefs();
        } catch (e) {
          this.logout();
        }
      }
    },

    applyTheme() {
      const root = document.documentElement;
      // Light-first (ClickUp / Monday style). Dark only when user explicitly chooses it.
      if (this.theme === 'dark') {
        root.classList.add('dark');
      } else {
        root.classList.remove('dark');
        this.theme = 'light';
      }
      localStorage.setItem('plan365_theme', this.theme);
    },
    toggleTheme() {
      // Disabled sementara — pakai dark mode default
      this.theme = 'dark';
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
        await this.loadDashboard();
        this.view = 'dashboard';
        this.connectRealtime();
        await this.loadTemplates();
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
      this.disconnectRealtime();
      this.token = null;
      this.user = null;
      localStorage.removeItem('plan365_token');
    },

    async loadProjects() {
      const q = [];
      if (this.projectFilterStatus) q.push('status=' + encodeURIComponent(this.projectFilterStatus));
      if (this.showArchivedProjects) q.push('include_archived=true');
      const qs = q.length ? '?' + q.join('&') : '';
      this.projects = await this.api('/api/projects' + qs);
    },
    async loadUsers() {
      this.users = await this.api('/api/users');
    },
    async loadTasks() {
      let q = [];
      if (this.currentProject) q.push('project_id=' + this.currentProject.id);
      if (this.filterTypes?.length) q.push('type=' + encodeURIComponent(this.filterTypes.join(',')));
      if (this.filterStatuses?.length) q.push('status=' + encodeURIComponent(this.filterStatuses.join(',')));
      if (this.filterPriorities?.length) q.push('priority=' + encodeURIComponent(this.filterPriorities.join(',')));
      const qs = q.length ? '?' + q.join('&') : '';
      this.tasks = await this.api('/api/tasks' + qs);
      this._ganttFingerprint = null;
      if (this.subView === 'gantt') this.scheduleRenderGantt(0);
      if (this.subView === 'kanban' && this.initKanban) this.$nextTick(() => this.initKanban());
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

    async deleteProject(p) {
      if (!confirm('Hapus project "' + p.name + '"?')) return;
      const cascade = confirm(
        'Hapus juga semua task di dalam project ini?\n\n' +
        'OK = hapus project + semua task terkait\n' +
        'Cancel = hapus project saja (task menjadi tanpa project)'
      );
      try {
        await this.api('/api/projects/' + p.id + (cascade ? '?cascade=true' : ''), { method: 'DELETE' });
        this.projects = this.projects.filter(x => x.id !== p.id);
        if (this.currentProject && this.currentProject.id === p.id) {
          this.currentProject = null;
          this.view = 'projects';
          this.tasks = [];
        }
        this.showToast(cascade ? 'Project + tasks dihapus' : 'Project dihapus (tasks tetap)');
        this.loadProjects();
      } catch (e) {
        this.showToast(e.message);
      }
    },


    openEditProject(p) {
      this.editProject = {
        id: p.id,
        name: p.name || '',
        description: p.description || '',
        color: p.color || '#3b82f6',
        status: p.status || 'Active',
        start_date: p.start_date || '',
        due_date: p.due_date || '',
        reference: p.reference || '',
        supporting_data: p.supporting_data || ''
      };
      this.showEditProject = true;
    },
    async saveEditProject() {
      if (!this.editProject?.id) return;
      if (!(this.editProject.name || '').trim()) {
        this.showToast('Nama project wajib');
        return;
      }
      try {
        const body = {
          name: this.editProject.name,
          description: this.editProject.description,
          color: this.editProject.color,
          status: this.editProject.status,
          start_date: this.editProject.start_date || null,
          due_date: this.editProject.due_date || null,
          reference: this.editProject.reference || null,
          supporting_data: this.editProject.supporting_data || null
        };
        const updated = await this.api('/api/projects/' + this.editProject.id, { method: 'PUT', body });
        const i = this.projects.findIndex(x => x.id === updated.id);
        if (i >= 0) this.projects[i] = { ...this.projects[i], ...updated };
        if (this.currentProject?.id === updated.id) this.currentProject = { ...this.currentProject, ...updated };
        this.showEditProject = false;
        this.showToast('Project updated');
      } catch (e) {
        this.showToast(e.message);
      }
    },
    projectStatusClass(s) {
      const map = {
        'Active': 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
        'On Hold': 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
        'Completed': 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
        'Archived': 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'
      };
      return map[s] || map['Active'];
    },
    async createProject() {
      if (!this.newProject.name.trim()) return;
      try {
        const body = { ...this.newProject };
        if (this.draftTemplateTasks.length) {
          body.template_tasks = this.draftTemplateTasks.map(t => ({
            title: t.title,
            type: t.type,
            priority: t.priority,
            effort: Number(t.effort) || 0,
            offset_start_days: Number(t.offset_start_days) || 0,
            duration_days: Number(t.duration_days) || 0,
            is_milestone: !!t.is_milestone,
            depends_on: (t.depends_on || []).map(Number).filter(n => !isNaN(n))
          }));
          // custom list takes precedence; keep template_id for audit optional
        } else if (!body.template_id) {
          delete body.template_id;
        }
        delete body.reference;
        delete body.supporting_data;
        const p = await this.api('/api/projects', { method: 'POST', body });
        this.projects.push(p);
        this.showNewProject = false;
        this.newProjectStep = 1;
        this.draftTemplateTasks = [];
        this.newProject = { name: '', description: '', color: '#3b82f6', status: 'Active', start_date: '', due_date: '', reference: '', supporting_data: '', template_id: '' };
        const n = p.template_applied?.tasks_created || 0;
        if (n) this.showToast('Project created · ' + n + ' tasks');
        else this.showToast('Project created');
        await this.loadProjects();
        this.selectProject(p);
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
      try {
        this.settings = await this.api('/api/settings');
        const s = this.settings || {};
        const arr = (v) => Array.isArray(v) ? v : (typeof v === 'string' ? (()=>{ try { return JSON.parse(v); } catch { return v.split(',').map(x=>x.trim()).filter(Boolean); } })() : []);
        if (s.task_types) this.types = arr(s.task_types);
        if (s.priorities) this.priorities = arr(s.priorities);
        if (s.statuses) this.statuses = arr(s.statuses);
        this.settingsEdit = {
          task_types: (this.types || []).join(', '),
          priorities: (this.priorities || []).join(', '),
          statuses: (this.statuses || []).join(', '),
          default_type: s.default_type || this.types[0] || 'Others',
          default_priority: s.default_priority || 'Medium',
          default_status: s.default_status || 'Todo',
        };
      } catch(e) {}
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


    get filteredTasks() {
      let list = this.tasks || [];
      const q = (this.searchQuery || '').trim().toLowerCase();
      if (q) {
        list = list.filter(t =>
          (t.title || '').toLowerCase().includes(q) ||
          (t.project_name || '').toLowerCase().includes(q) ||
          (t.assignee_name || '').toLowerCase().includes(q) ||
          (t.type || '').toLowerCase().includes(q) ||
          (t.status || '').toLowerCase().includes(q)
        );
      }
      return list;
    },
    statusPill(status) {
      const map = {
        'Todo': 'st-todo',
        'In Progress': 'st-in-progress',
        'Review': 'st-review',
        'Testing': 'st-testing',
        'Done': 'st-done',
        'Blocked': 'st-blocked',
        'Handoff': 'st-handoff',
        'Backlog': 'st-backlog'
      };
      return map[status] || 'st-todo';
    },
    isOverdue(task) {
      if (!task.due_date || task.status === 'Done' || task.status === 'Handoff') return false;
      const d = new Date(task.due_date + 'T23:59:59');
      return d < new Date();
    },


    parseCsvList(str) {
      return (str || '').split(',').map(s => s.trim()).filter(Boolean);
    },
    async saveTaskParams() {
      try {
        const payload = {
          task_types: this.parseCsvList(this.settingsEdit.task_types),
          priorities: this.parseCsvList(this.settingsEdit.priorities),
          statuses: this.parseCsvList(this.settingsEdit.statuses),
          default_type: this.settingsEdit.default_type || 'Others',
          default_priority: this.settingsEdit.default_priority || 'Medium',
          default_status: this.settingsEdit.default_status || 'Todo',
        };
        await this.api('/api/settings', { method: 'PUT', body: payload });
        this.types = payload.task_types;
        this.priorities = payload.priorities;
        this.statuses = payload.statuses;
        this.showToast('Task parameters saved');
        await this.loadSettings();
      } catch (e) { this.showToast(e.message || 'Save failed'); }
    },
    async createUser() {
      try {
        await this.api('/api/users', { method: 'POST', body: this.newUser });
        this.showNewUser = false;
        this.newUser = { username: '', email: '', password: '', full_name: '', role: 'user' };
        this.users = await this.api('/api/users');
        this.showToast('User created');
      } catch (e) { this.showToast(e.message || 'Create failed'); }
    },
    async updateUserRole(u, role) {
      try {
        await this.api('/api/users/' + u.id, { method: 'PATCH', body: { role } });
        this.users = await this.api('/api/users');
        this.showToast('Role updated');
      } catch (e) { this.showToast(e.message || 'Update failed'); }
    },
    async deactivateUser(u) {
      if (!confirm('Deactivate user ' + u.username + '?')) return;
      try {
        await this.api('/api/users/' + u.id, { method: 'PATCH', body: { is_active: false } });
        this.users = await this.api('/api/users');
        this.showToast('User deactivated');
      } catch (e) { this.showToast(e.message || 'Failed'); }
    },
    async toggleRegistration() {
      try {
        const cur = this.settings.allow_registration === true || this.settings.allow_registration === 'true';
        await this.api('/api/settings', { method: 'PUT', body: { allow_registration: (!cur).toString() } });
        await this.loadSettings();
        this.showToast('Registration setting updated');
      } catch (e) { this.showToast(e.message || 'Failed'); }
    },
    toggleSidebar() {
      this.sidebarCollapsed = !this.sidebarCollapsed;
      localStorage.setItem('plan365_sidebar', this.sidebarCollapsed ? '1' : '0');
      if (this.subView === 'gantt') this.scheduleRenderGantt(0);
    },
    get ganttOverallProgress() {
      const list = this.ganttVisibleTasks || [];
      if (!list.length) return 0;
      const sum = list.reduce((a, t) => a + (t.progress || 0), 0);
      return Math.round(sum / list.length);
    },

    async loadWorkload() {
      try {
        const q = this.currentProject ? ('?project_id=' + this.currentProject.id) : '';
        this.workload = await this.api('/api/workload' + q);
      } catch (e) {
        this.workload = { assignees: [], milestones_upcoming: [] };
      }
    },
    async saveTaskBaseline(taskId) {
      const id = taskId || this.detailTask?.id;
      if (!id) return;
      try {
        const r = await this.api('/api/tasks/' + id + '/baseline', { method: 'POST', body: {} });
        this.showToast('Baseline saved');
        await this.loadTasks();
        if (this.detailTask?.id === id) {
          this.detailForm.baseline_start = r.baseline_start;
          this.detailForm.baseline_due = r.baseline_due;
        }
      } catch (e) { this.showToast(e.message); }
    },
    async saveProjectBaseline() {
      const pid = this.currentProject?.id;
      if (!pid) { this.showToast('Pilih project dulu'); return; }
      try {
        const r = await this.api('/api/projects/' + pid + '/baseline', { method: 'POST', body: {} });
        this.showToast('Baseline project: ' + (r.tasks_updated || 0) + ' tasks');
        await this.loadTasks();
        this.scheduleRenderGantt && this.scheduleRenderGantt(0);
      } catch (e) { this.showToast(e.message); }
    },
    toggleCascadeSchedule() {
      this.cascadeSchedule = !this.cascadeSchedule;
      localStorage.setItem('plan365_cascade', this.cascadeSchedule ? '1' : '0');
      this.showToast(this.cascadeSchedule ? 'Auto-shift FS: ON' : 'Auto-shift FS: OFF');
    },
    _prepareGanttSvgClone() {
      const svg = document.querySelector('#gantt-target svg');
      if (!svg) return null;
      // ensure fills inlined before clone
      if (this._inlineGanttBarFills) this._inlineGanttBarFills();
      else if (window.Plan365Gantt && Plan365Gantt._inlineGanttBarFills) {
        Plan365Gantt._inlineGanttBarFills.call(this);
      }
      const clone = svg.cloneNode(true);
      const bbox = svg.getBBox ? svg.getBBox() : null;
      const w = Math.ceil(Math.max(svg.clientWidth || 0, svg.width?.baseVal?.value || 0, bbox ? bbox.x + bbox.width : 0, 800));
      const h = Math.ceil(Math.max(svg.clientHeight || 0, svg.height?.baseVal?.value || 0, bbox ? bbox.y + bbox.height : 0, 400));
      clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
      clone.setAttribute('width', String(w));
      clone.setAttribute('height', String(h));
      if (!clone.getAttribute('viewBox')) {
        clone.setAttribute('viewBox', `0 0 ${w} ${h}`);
      }
      const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      bg.setAttribute('x', '0');
      bg.setAttribute('y', '0');
      bg.setAttribute('width', String(w));
      bg.setAttribute('height', String(h));
      bg.setAttribute('fill', '#ffffff');
      clone.insertBefore(bg, clone.firstChild);
      // strip external class reliance — copy fill from computed if still missing
      clone.querySelectorAll('[class]').forEach((el) => {
        if (!el.getAttribute('fill') && el.tagName === 'rect') {
          // leave
        }
      });
      return { clone, w, h };
    },
    exportGanttSvg() {
      const prep = this._prepareGanttSvgClone();
      if (!prep) { this.showToast('Gantt belum dirender'); return; }
      const xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + new XMLSerializer().serializeToString(prep.clone);
      const blob = new Blob([xml], { type: 'image/svg+xml;charset=utf-8' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'plan365-gantt.svg';
      a.click();
      URL.revokeObjectURL(a.href);
      this.showToast('Exported Gantt SVG');
    },
    exportGanttPng() {
      const prep = this._prepareGanttSvgClone();
      if (!prep) { this.showToast('Gantt belum dirender'); return; }
      const xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + new XMLSerializer().serializeToString(prep.clone);
      const url = URL.createObjectURL(new Blob([xml], { type: 'image/svg+xml;charset=utf-8' }));
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        canvas.width = prep.w;
        canvas.height = prep.h;
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0);
        URL.revokeObjectURL(url);
        canvas.toBlob((blob) => {
          if (!blob) { this.showToast('PNG export gagal'); return; }
          const a = document.createElement('a');
          a.href = URL.createObjectURL(blob);
          a.download = 'plan365-gantt.png';
          a.click();
          URL.revokeObjectURL(a.href);
          this.showToast('Exported Gantt PNG');
        }, 'image/png');
      };
      img.onerror = () => { URL.revokeObjectURL(url); this.showToast('PNG export gagal — coba SVG'); };
      img.src = url;
    },
    pieSlices(items, valueKey) {
      const colors = ['#6366f1','#0ea5e9','#10b981','#f59e0b','#ef4444','#8b5cf6','#64748b','#ec4899','#14b8a6'];
      const data = (items || []).map((it, i) => ({
        label: it.assignee_name || it.label || '—',
        value: Number(it[valueKey] || 0),
        color: colors[i % colors.length],
      })).filter(d => d.value > 0);
      const total = data.reduce((s, d) => s + d.value, 0);
      if (!total) {
        return { slices: [], total: 0, gradient: 'conic-gradient(#e2e8f0 0deg 360deg)' };
      }
      let deg = 0;
      const parts = [];
      const slices = [];
      for (const d of data) {
        const sweep = (d.value / total) * 360;
        parts.push(d.color + ' ' + deg + 'deg ' + (deg + sweep) + 'deg');
        const pct = Math.round((d.value / total) * 100);
        slices.push({ ...d, pct, startDeg: deg, sweep });
        deg += sweep;
      }
      return { slices, total, gradient: 'conic-gradient(' + parts.join(',') + ')' };
    },
    get workloadOpenPie() {
      return this.pieSlices(this.workload?.assignees || [], 'open_count');
    },
    toggleFilter(arrName, value) {
      const arr = this[arrName] || [];
      const i = arr.indexOf(value);
      if (i >= 0) arr.splice(i, 1);
      else arr.push(value);
      this[arrName] = [...arr];
      this.loadTasks();
    },
    clearFilters() {
      this.filterTypes = [];
      this.filterStatuses = [];
      this.filterPriorities = [];
      this.loadTasks();
    },
    capacityBarColor(util) {
      if (util > 100) return '#ef4444';
      if (util >= 85) return '#f59e0b';
      if (util >= 40) return '#10b981';
      return '#6366f1';
    },
    async saveAssigneeCapacity(a) {
      if (!a.assignee_id || this.user?.role !== 'admin') return;
      try {
        await this.api('/api/users/' + a.assignee_id, {
          method: 'PATCH',
          body: { weekly_capacity: parseInt(a.weekly_capacity) || 40 }
        });
        this.showToast('Capacity updated');
        await this.loadWorkload();
        this.users = await this.api('/api/users');
      } catch (e) { this.showToast(e.message); }
    },
    get workloadOverduePie() {
      return this.pieSlices(this.workload?.assignees || [], 'overdue_count');
    },
    editUser: null,
    editUserForm: {},
    openEditUser(u) {
      this.editUser = u;
      this.editUserForm = {
        full_name: u.full_name || '',
        email: u.email || '',
        role: u.role || 'user',
        is_active: !!u.is_active,
        password: '',
        weekly_capacity: u.weekly_capacity ?? 40
      };
    },
    async saveEditUser() {
      if (!this.editUser) return;
      try {
        const body = {
          full_name: this.editUserForm.full_name,
          email: this.editUserForm.email,
          role: this.editUserForm.role,
          is_active: this.editUserForm.is_active,
          weekly_capacity: parseInt(this.editUserForm.weekly_capacity) || 40
        };
        if (this.editUserForm.password) body.password = this.editUserForm.password;
        await this.api('/api/users/' + this.editUser.id, { method: 'PATCH', body });
        this.editUser = null;
        this.users = await this.api('/api/users');
        this.showToast('User updated');
      } catch (e) { this.showToast(e.message); }
    },

    async loadDashboard() {
      this.dashLoading = true;
      try {
        this.dashboard = await this.api('/api/dashboard');
      } catch (e) {
        this.dashboard = null;
        this.showToast(e.message || 'Dashboard failed');
      } finally {
        this.dashLoading = false;
      }
    },
    healthBadge(h) {
      return {
        completed: 'bg-emerald-100 text-emerald-700',
        on_track: 'bg-sky-100 text-sky-700',
        at_risk: 'bg-amber-100 text-amber-800',
        delayed: 'bg-red-100 text-red-700',
      }[h] || 'bg-slate-100 text-slate-600';
    },
    healthLabel(h) {
      return { completed: 'Completed', on_track: 'On track', at_risk: 'At risk', delayed: 'Delayed' }[h] || h;
    },
    gaugeArc(pct) {
      // legacy path (unused if dash used)
      const p = Math.max(0, Math.min(100, Number(pct) || 0));
      return p;
    },
    gaugeDash(pct) {
      const C = Math.PI * 60; // r=60
      const p = Math.max(0, Math.min(100, Number(pct) || 0));
      return ((p / 100) * C) + ' ' + C;
    },
    gaugeOffset(pct) {
      const C = Math.PI * 60;
      const p = Math.max(0, Math.min(100, Number(pct) || 0));
      return C - (p / 100) * C;
    },

    connectRealtime() {
      if (!this.token || typeof EventSource === 'undefined') return;
      this.disconnectRealtime();
      const url = '/api/events?token=' + encodeURIComponent(this.token);
      try {
        const es = new EventSource(url);
        this._es = es;
        this.rtStatus = 'connecting';
        es.addEventListener('connected', () => {
          this.rtConnected = true;
          this.rtStatus = 'live';
        });
        es.addEventListener('ping', () => {
          this.rtConnected = true;
          this.rtStatus = 'live';
        });
        const onChange = (ev) => {
          this.rtConnected = true;
          this.rtStatus = 'live';
          let data = {};
          try { data = JSON.parse(ev.data || '{}'); } catch (_) {}
          this._onRealtimeEvent(data.type || ev.type, data.data || data);
        };
        ['task.created','task.updated','task.deleted','project.created','project.updated','project.deleted','dependency.changed'].forEach(t => {
          es.addEventListener(t, onChange);
        });
        es.onerror = () => {
          this.rtConnected = false;
          this.rtStatus = 'reconnect';
          // EventSource auto-reconnects
        };
      } catch (e) {
        this.rtStatus = 'error';
      }
    },
    disconnectRealtime() {
      if (this._es) {
        try { this._es.close(); } catch (_) {}
        this._es = null;
      }
      this.rtConnected = false;
      this.rtStatus = 'off';
    },
    _onRealtimeEvent(type, data) {
      // debounce burst updates (e.g. cascade shifts)
      if (this._rtDebounce) clearTimeout(this._rtDebounce);
      this._rtDebounce = setTimeout(async () => {
        try {
          if (type && type.startsWith('project')) {
            await this.loadProjects();
          }
          if (type && (type.startsWith('task') || type.startsWith('dependency') || type.startsWith('project'))) {
            await this.loadTasks();
            if (this.view === 'dashboard') await this.loadDashboard();
            if (this.view === 'workload') await this.loadWorkload();
            if (this.subView === 'gantt') this.scheduleRenderGantt?.(0);
            if (this.subView === 'kanban') this.$nextTick(() => this.initKanban?.());
          }
        } catch (_) { /* ignore transient */ }
      }, 350);
    },

    async loadTemplates() {
      try {
        this.projectTemplates = await this.api('/api/templates');
        this.templateEdit = JSON.parse(JSON.stringify(this.projectTemplates));
      } catch (e) {
        this.projectTemplates = [];
      }
    },
    async saveTemplates() {
      try {
        let body = this.templateEdit;
        if (this.templateEditMode === 'json') {
          body = JSON.parse(this.templateEditJson || '[]');
        }
        // Pastikan selalu mengirim array lengkap, bukan objek tunggal
        if (!Array.isArray(body)) {
          body = this.projectTemplates.map(t => t.id === body.id ? body : t);
        }
        this.projectTemplates = await this.api('/api/templates', { method: 'PUT', body });
        this.templateEdit = JSON.parse(JSON.stringify(this.projectTemplates));
        this.templateEditJson = JSON.stringify(this.projectTemplates, null, 2);
        this.showToast('Templates saved');
      } catch (e) {
        this.showToast(e.message || 'Save templates failed');
      }
    },
    async resetTemplates() {
      if (!confirm('Reset to 3 default presets?')) return;
      try {
        this.projectTemplates = await this.api('/api/templates/reset', { method: 'POST', body: {} });
        this.templateEdit = JSON.parse(JSON.stringify(this.projectTemplates));
        this.templateEditJson = JSON.stringify(this.projectTemplates, null, 2);
        this.showToast('Templates reset');
      } catch (e) { this.showToast(e.message); }
    },
    addEmptyTemplate() {
      this.templatesOpen = true;
      this.templateEditMode = 'list';
      if (!Array.isArray(this.templateEdit)) this.templateEdit = [];
      const id = 'custom-' + Date.now();
      this.templateEdit = [
        ...this.templateEdit,
        {
          id,
          name: 'New template',
          description: '',
          tasks: [{
            title: 'Task 1', type: 'Others', priority: 'Medium', effort: 4,
            offset_start_days: 0, duration_days: 2, is_milestone: false, depends_on: []
          }]
        }
      ];
      this.showToast('Template row added — edit then Save templates');
    },
    removeTemplate(idx) {
      this.templateEdit = this.templateEdit.filter((_, i) => i !== idx);
    },
    addTemplateTask(tIdx) {
      const t = this.templateEdit[tIdx];
      if (!t.tasks) t.tasks = [];
      t.tasks.push({
        title: 'New task', type: 'CAD', priority: 'Medium', effort: 4,
        offset_start_days: 0, duration_days: 2, is_milestone: false, depends_on: []
      });
    },
    removeTemplateTask(tIdx, taskIdx) {
      this.templateEdit[tIdx].tasks.splice(taskIdx, 1);
    },

    openNewProject() {
      this.newProject = { name: '', description: '', color: '#3b82f6', status: 'Active', start_date: '', due_date: '', reference: '', supporting_data: '', template_id: '' };
      this.draftTemplateTasks = [];
      this.newProjectStep = 1;
      this.showNewProject = true;
      this.loadTemplates();
    },
    loadDraftFromTemplate() {
      const id = this.newProject.template_id;
      if (!id) {
        this.draftTemplateTasks = [];
        return;
      }
      const tpl = (this.projectTemplates || []).find(t => t.id === id);
      if (!tpl) {
        this.draftTemplateTasks = [];
        return;
      }
      this.draftTemplateTasks = (tpl.tasks || []).map((t, i) => ({
        title: t.title,
        type: t.type || 'Others',
        priority: t.priority || 'Medium',
        effort: t.effort || 0,
        offset_start_days: t.offset_start_days || 0,
        duration_days: t.duration_days || 0,
        is_milestone: !!t.is_milestone,
        depends_on: Array.isArray(t.depends_on) ? [...t.depends_on] : [],
        _i: i
      }));
    },
    newProjectNext() {
      if (!this.newProject.name || !this.newProject.name.trim()) {
        this.showToast('Nama project wajib');
        return;
      }
      if (this.newProject.template_id) {
        if (!this.draftTemplateTasks.length) this.loadDraftFromTemplate();
        this.newProjectStep = 2;
      } else {
        this.createProject();
      }
    },
    newProjectBack() {
      this.newProjectStep = 1;
    },
    addDraftTask() {
      this.draftTemplateTasks.push({
        title: 'New task',
        type: 'CAD',
        priority: 'Medium',
        effort: 4,
        offset_start_days: 0,
        duration_days: 2,
        is_milestone: false,
        depends_on: []
      });
    },
    removeDraftTask(idx) {
      this.draftTemplateTasks.splice(idx, 1);
      // clean depends_on pointing past end
      this.draftTemplateTasks.forEach(t => {
        t.depends_on = (t.depends_on || []).filter(d => d >= 0 && d < this.draftTemplateTasks.length);
      });
    },
    moveDraftTask(idx, dir) {
      const j = idx + dir;
      if (j < 0 || j >= this.draftTemplateTasks.length) return;
      const arr = this.draftTemplateTasks;
      const tmp = arr[idx];
      arr[idx] = arr[j];
      arr[j] = tmp;
      this.draftTemplateTasks = [...arr];
    },

    async loadAiAnalyze() {
      this.aiLoading = true;
      try {
        this.aiAnalysis = await this.api('/api/ai/analyze');
      } catch (e) {
        this.showToast(e.message || 'AI analyze failed');
      } finally {
        this.aiLoading = false;
      }
    },
    async loadAiSettings() {
      try {
        this.aiSettings = await this.api('/api/ai/settings');
        this.aiSettingsForm = {
          ai_enabled: !!this.aiSettings.ai_enabled,
          ai_api_url: this.aiSettings.ai_api_url || '',
          ai_model: this.aiSettings.ai_model || '',
          ai_system_prompt: this.aiSettings.ai_system_prompt || '',
          ai_api_key: ''
        };
      } catch (e) { /* ignore */ }
    },
    async saveAiSettings() {
      try {
        const body = {
          ai_enabled: !!this.aiSettingsForm.ai_enabled,
          ai_api_url: this.aiSettingsForm.ai_api_url,
          ai_model: this.aiSettingsForm.ai_model,
          ai_system_prompt: this.aiSettingsForm.ai_system_prompt
        };
        if (this.aiSettingsForm.ai_api_key && !this.aiSettingsForm.ai_api_key.startsWith('••')) {
          body.ai_api_key = this.aiSettingsForm.ai_api_key;
        }
        await this.api('/api/ai/settings', { method: 'PUT', body });
        await this.loadAiSettings();
        this.showToast('AI settings saved');
      } catch (e) {
        this.showToast(e.message || 'Save failed');
      }
    },
    async runAiChat() {
      const msg = (this.aiChatInput || '').trim();
      if (!msg) return;
      this.aiLoading = true;
      this.aiChatLog = [...this.aiChatLog, { role: 'user', text: msg }];
      this.aiChatInput = '';
      try {
        const res = await this.api('/api/ai/chat', { method: 'POST', body: { message: msg } });
        const reply = res.reply || JSON.stringify(res);
        this.aiChatReply = reply;
        this.aiChatLog = [...this.aiChatLog, { role: 'assistant', text: reply, mode: res.mode }];
        if (res.analysis) this.aiAnalysis = res.analysis;
      } catch (e) {
        this.aiChatLog = [...this.aiChatLog, { role: 'assistant', text: e.message || 'Error' }];
      } finally {
        this.aiLoading = false;
      }
    },
    async loadAiSyncPreview() {
      try {
        const data = await this.api('/api/ai/sync');
        this.aiPreview = JSON.stringify(data, null, 2);
      } catch (e) {
        this.showToast(e.message);
      }
    },
    openAiView() {
      this.view = 'ai';
      this.loadAiAnalyze();
      this.loadAiSettings();
    },
    severityClass(s) {
      const map = {
        critical: 'ui-badge-danger',
        high: 'ui-badge-warning',
        medium: 'ui-badge-info',
        low: 'ui-badge-secondary'
      };
      return map[s] || 'ui-badge-secondary';
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

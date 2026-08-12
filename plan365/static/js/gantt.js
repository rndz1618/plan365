/** Plan365 Gantt mixin — optimized render for low-RAM SBC */
window.Plan365Gantt = {
  // ---- Gantt filters / helpers ----
  taskMatchesGanttFilter(t) {
    if (this.ganttFilterType && t.type !== this.ganttFilterType) return false;
    if (this.ganttFilterStatus && t.status !== this.ganttFilterStatus) return false;
    if (this.ganttFilterAssignee === 'none') {
      if (t.assignee_id) return false;
    } else if (this.ganttFilterAssignee) {
      if (String(t.assignee_id) !== String(this.ganttFilterAssignee)) return false;
    }
    if (this.ganttFilterBlocked && !this.isTaskBlocked(t)) return false;
    return true;
  },
  clearGanttFilters() {
    this.ganttFilterType = '';
    this.ganttFilterStatus = '';
    this.ganttFilterAssignee = '';
    this.ganttFilterBlocked = false;
    this.ganttShowCritical = false;
    this.scheduleRenderGantt();
  },
  taskDurationDays(t) {
    const s = t.start_date || t.due_date;
    const e = t.due_date || t.start_date;
    if (!s || !e) return 1;
    const a = new Date(s + 'T00:00:00');
    const b = new Date(e + 'T00:00:00');
    const d = Math.round((b - a) / 86400000);
    return Math.max(1, d);
  },
  computeCriticalPathIds(taskList) {
    /** Longest path by duration along FS edges (predecessor_ids). */
    if (!taskList.length) return new Set();
    const byId = Object.create(null);
    for (const t of taskList) byId[t.id] = t;
    const ids = taskList.map(t => t.id);
    const preds = Object.create(null);
    for (const t of taskList) {
      preds[t.id] = (t.predecessor_ids || []).filter(pid => byId[pid]);
    }
    const indeg = Object.create(null);
    const succ = Object.create(null);
    for (const id of ids) {
      indeg[id] = 0;
      succ[id] = [];
    }
    for (const id of ids) {
      for (const p of preds[id]) {
        indeg[id]++;
        succ[p].push(id);
      }
    }
    const q = ids.filter(id => indeg[id] === 0);
    const order = [];
    while (q.length) {
      const u = q.shift();
      order.push(u);
      for (const v of succ[u]) {
        indeg[v]--;
        if (indeg[v] === 0) q.push(v);
      }
    }
    if (order.length !== ids.length) return new Set(); // cycle — skip
    const dist = Object.create(null);
    const parent = Object.create(null);
    for (const id of ids) {
      dist[id] = this.taskDurationDays(byId[id]);
      parent[id] = null;
    }
    for (const u of order) {
      for (const v of succ[u]) {
        const cand = dist[u] + this.taskDurationDays(byId[v]);
        if (cand > dist[v]) {
          dist[v] = cand;
          parent[v] = u;
        }
      }
    }
    let end = null;
    let best = -1;
    for (const id of ids) {
      if (dist[id] > best) {
        best = dist[id];
        end = id;
      }
    }
    const path = new Set();
    while (end != null) {
      path.add(end);
      end = parent[end];
    }
    return path;
  },

  get ganttGroups() {
    const map = new Map();
    const filtered = this.tasks.filter(t => this.taskMatchesGanttFilter(t));
    // Prefer dated tasks first (stable order for chart alignment)
    const ordered = filtered.slice().sort((a, b) => {
      const ad = !!(a.start_date || a.due_date);
      const bd = !!(b.start_date || b.due_date);
      if (ad !== bd) return ad ? -1 : 1;
      return String(a.project_id).localeCompare(String(b.project_id)) ||
        String(a.start_date || '').localeCompare(String(b.start_date || '')) ||
        (a.id - b.id);
    });
    for (const t of ordered) {
      const key = String(t.project_id ?? 'none');
      let g = map.get(key);
      if (!g) {
        g = {
          key,
          name: t.project_name || 'No project',
          color: t.project_color || '#3b82f6',
          tasks: []
        };
        map.set(key, g);
      }
      g.tasks.push(t);
    }
    return Array.from(map.values());
  },
  get ganttVisibleTasks() {
    return this.ganttGroups
      .filter(g => !this.ganttCollapsed[g.key])
      .flatMap(g => g.tasks);
  },
  get ganttVisibleCount() {
    return this.ganttVisibleTasks.length;
  },
  get ganttTaskList() {
    return this.ganttVisibleTasks;
  },

  toggleGanttGroup(key) {
    this.ganttCollapsed = {
      ...this.ganttCollapsed,
      [key]: !this.ganttCollapsed[key]
    };
    this.scheduleRenderGantt();
  },
  ganttCollapseAll() {
    const next = {};
    for (const g of this.ganttGroups) next[g.key] = true;
    this.ganttCollapsed = next;
    this.scheduleRenderGantt();
  },
  ganttExpandAll() {
    this.ganttCollapsed = {};
    this.scheduleRenderGantt();
  },
  highlightGantt(id) {
    this.detailTask = this.tasks.find(t => t.id === id) || this.detailTask;
  },

  /** Debounced public entry — collapses rapid filter/toggle/resize calls */
  scheduleRenderGantt(delay = 40) {
    if (this._ganttTimer) clearTimeout(this._ganttTimer);
    this._ganttTimer = setTimeout(() => {
      this._ganttTimer = null;
      this.renderGantt();
    }, delay);
  },

  /** Fingerprint of chart payload (skip full rebuild when unchanged) */
  _ganttDataFingerprint(items, mode, criticalOn) {
    let h = mode + '|' + (criticalOn ? '1' : '0') + '|' + items.length;
    for (const it of items) {
      h += '|' + it.id + ':' + it.start + ':' + it.end + ':' + it.progress +
        ':' + (it.dependencies || '') + ':' + (it.custom_class || '');
    }
    return h;
  },

  _applyGanttHeaderContrast() {
    const root = document.getElementById('gantt-target');
    if (!root) return;
    const headers = root.querySelectorAll('.grid-header');
    for (let i = 0; i < headers.length; i++) {
      headers[i].setAttribute('fill', '#1e293b');
    }
    const labels = root.querySelectorAll('.upper-text, .lower-text');
    for (let i = 0; i < labels.length; i++) {
      labels[i].setAttribute('fill', '#f8fafc');
      labels[i].style.fill = '#f8fafc';
      labels[i].style.fontWeight = '700';
    }
  },

  _destroyGantt() {
    const el = document.getElementById('gantt-target');
    if (this.ganttInstance) {
      try {
        // Frappe has no official destroy; drop refs + clear DOM
        this.ganttInstance = null;
      } catch (_) { /* ignore */ }
    }
    if (el) {
      // Remove listeners by replacing node (cheaper than walking SVG)
      while (el.firstChild) el.removeChild(el.firstChild);
    }
    this._ganttFingerprint = null;
  },

  /**
   * Build Frappe items from current visible/dated tasks.
   * VisibleIds set built once (not per-task).
   */
  _buildGanttItems() {
    const visible = this.ganttVisibleTasks;
    const dated = [];
    for (let i = 0; i < visible.length; i++) {
      const t = visible[i];
      if (t.start_date || t.due_date) dated.push(t);
    }
    const critical = this.ganttShowCritical
      ? this.computeCriticalPathIds(dated)
      : null;
    const visibleIds = new Set();
    for (let i = 0; i < visible.length; i++) {
      visibleIds.add(String(visible[i].id));
    }
    const items = new Array(dated.length);
    for (let i = 0; i < dated.length; i++) {
      const t = dated[i];
      let start = t.start_date || t.due_date;
      let end = t.due_date || t.start_date;
      if (start === end) {
        // Frappe needs end > start; +1 day
        const d = new Date(end + 'T00:00:00');
        d.setDate(d.getDate() + 1);
        end = d.toISOString().slice(0, 10);
      }
      const preds = t.predecessor_ids || [];
      const predParts = [];
      for (let j = 0; j < preds.length; j++) {
        const id = String(preds[j]);
        if (visibleIds.has(id)) predParts.push(id);
      }
      const typeCls = 'gantt-' + (t.type || 'Others').replace(/\s+/g, '-').toLowerCase();
      const critCls = critical && critical.has(t.id) ? ' gantt-critical' : '';
      items[i] = {
        id: String(t.id),
        name: t.title,
        start,
        end,
        progress: t.progress || 0,
        dependencies: predParts.join(','),
        custom_class: typeCls + critCls
      };
    }
    return items;
  },

  renderGantt() {
    if (this.subView !== 'gantt') return;
    const el = document.getElementById('gantt-target');
    if (!el || typeof Gantt === 'undefined') return;

    const mode = this.ganttViewMode || 'Week';
    const items = this._buildGanttItems();
    const fp = this._ganttDataFingerprint(items, mode, !!this.ganttShowCritical);

    // Same data + mode → skip rebuild (e.g. unrelated Alpine re-eval)
    if (this.ganttInstance && this._ganttFingerprint === fp) {
      return;
    }

    // Same task data, only view mode changed → use Frappe change_view_mode
    if (
      this.ganttInstance &&
      this._ganttFingerprint &&
      typeof this.ganttInstance.change_view_mode === 'function'
    ) {
      const prev = this._ganttFingerprint;
      // Compare without mode prefix (first segment)
      const prevBody = prev.slice(prev.indexOf('|'));
      const nextBody = fp.slice(fp.indexOf('|'));
      if (prevBody === nextBody) {
        try {
          this.ganttInstance.change_view_mode(mode);
          this._ganttFingerprint = fp;
          requestAnimationFrame(() => this._applyGanttHeaderContrast());
          return;
        } catch (_) {
          // fall through to full rebuild
        }
      }
    }

    if (items.length === 0) {
      this._destroyGantt();
      return;
    }

    // Soft cap: large boards stay responsive on 2GB SBC
    const MAX = 250;
    const chartItems = items.length > MAX ? items.slice(0, MAX) : items;

    const paint = () => {
      this._destroyGantt();
      try {
        this.ganttInstance = new Gantt('#gantt-target', chartItems, {
          view_mode: mode,
          bar_height: 22,
          padding: 14,
          // Lighter defaults
          column_width: mode === 'Day' ? 38 : mode === 'Week' ? 60 : 80,
          on_click: (task) => {
            const t = this.tasks.find(x => String(x.id) === task.id);
            if (t) this.openDetail(t);
          },
          on_date_change: async (task, start, end) => {
            const id = parseInt(task.id, 10);
            try {
              await this.api('/api/tasks/' + id, {
                method: 'PUT',
                body: {
                  start_date: start.toISOString().slice(0, 10),
                  due_date: end.toISOString().slice(0, 10),
                  cascade_schedule: this.cascadeSchedule !== false
                }
              });
              this.showToast('Tanggal diupdate');
              await this.loadTasks();
            } catch (e) {
              this.showToast(e.message);
            }
          }
        });
        this._ganttFingerprint = fp;
        requestAnimationFrame(() => {
          this._applyGanttHeaderContrast();
          this._inlineGanttBarFills();
          this.bindGanttScrollSync();
        });
      } catch (e) {
        console.warn('Gantt render error', e);
      }
    };

    // Yield to browser so UI stays responsive while SVG builds
    if (typeof requestAnimationFrame === 'function') {
      requestAnimationFrame(paint);
    } else {
      paint();
    }
  },

  _inlineGanttBarFills() {
    const root = document.getElementById('gantt-target');
    if (!root) return;
    const TYPE_FILL = {
      'gantt-2d-cad': '#0ea5e9',
      'gantt-cad': '#8b5cf6',
      'gantt-cam': '#f59e0b',
      'gantt-tools': '#10b981',
      'gantt-others': '#64748b',
    };
    root.querySelectorAll('.bar-wrapper').forEach((w) => {
      let fill = '#6366f1';
      const cls = w.getAttribute('class') || '';
      for (const [k, v] of Object.entries(TYPE_FILL)) {
        if (cls.includes(k)) { fill = v; break; }
      }
      if (cls.includes('gantt-critical')) fill = '#ef4444';
      const bar = w.querySelector('.bar');
      const prog = w.querySelector('.bar-progress');
      if (bar) {
        bar.setAttribute('fill', fill);
        bar.style.fill = fill;
      }
      if (prog) {
        // slightly darker progress
        prog.setAttribute('fill', fill);
        prog.style.fill = fill;
        prog.style.opacity = '0.85';
      }
      const label = w.querySelector('.bar-label');
      if (label) {
        label.setAttribute('fill', '#0f172a');
        label.style.fill = '#0f172a';
      }
    });
    // grid rows
    root.querySelectorAll('.grid-row').forEach((el, i) => {
      const f = i % 2 ? '#f8fafc' : '#ffffff';
      el.setAttribute('fill', f);
    });
  },

  bindGanttScrollSync() {
    const chart = document.querySelector('.zg-chart');
    const list = document.querySelector('.zg-list-scroll');
    if (!chart || !list) return;
    if (this._ganttScrollBound) {
      chart.removeEventListener('scroll', this._ganttScrollBound.chart);
      list.removeEventListener('scroll', this._ganttScrollBound.list);
    }
    let lock = false;
    const onChart = () => {
      if (lock) return;
      lock = true;
      list.scrollTop = chart.scrollTop;
      lock = false;
    };
    const onList = () => {
      if (lock) return;
      lock = true;
      chart.scrollTop = list.scrollTop;
      lock = false;
    };
    chart.addEventListener('scroll', onChart, { passive: true });
    list.addEventListener('scroll', onList, { passive: true });
    this._ganttScrollBound = { chart: onChart, list: onList };
  }
};

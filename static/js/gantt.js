/** Plan365 Gantt mixin — loaded before app.js */
window.Plan365Gantt = {
    // ---- Gantt ----
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
      this.$nextTick(() => this.renderGantt());
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
      const byId = {};
      for (const t of taskList) byId[t.id] = t;
      const ids = taskList.map(t => t.id);
      const preds = {};
      for (const t of taskList) {
        preds[t.id] = (t.predecessor_ids || []).filter(pid => byId[pid]);
      }
      // Kahn topo
      const indeg = {};
      const succ = {};
      for (const id of ids) { indeg[id] = 0; succ[id] = []; }
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
      const dist = {};
      const parent = {};
      for (const id of ids) { dist[id] = this.taskDurationDays(byId[id]); parent[id] = null; }
      for (const u of order) {
        for (const v of succ[u]) {
          const cand = dist[u] + this.taskDurationDays(byId[v]);
          if (cand > dist[v]) {
            dist[v] = cand;
            parent[v] = u;
          }
        }
      }
      let end = null, best = -1;
      for (const id of ids) {
        if (dist[id] > best) { best = dist[id]; end = id; }
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
      const ordered = [
        ...filtered.filter(t => t.start_date || t.due_date),
        ...filtered.filter(t => !t.start_date && !t.due_date)
      ];
      for (const t of ordered) {
        const key = String(t.project_id ?? 'none');
        if (!map.has(key)) {
          map.set(key, {
            key,
            name: t.project_name || 'No project',
            color: t.project_color || '#3b82f6',
            tasks: []
          });
        }
        map.get(key).tasks.push(t);
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
      this.$nextTick(() => this.renderGantt());
    },
    ganttCollapseAll() {
      const next = {};
      for (const g of this.ganttGroups) next[g.key] = true;
      this.ganttCollapsed = next;
      this.$nextTick(() => this.renderGantt());
    },
    ganttExpandAll() {
      this.ganttCollapsed = {};
      this.$nextTick(() => this.renderGantt());
    },
    highlightGantt(id) {
      this.detailTask = this.tasks.find(t => t.id === id) || this.detailTask;
    },
    renderGantt() {
      const el = document.getElementById('gantt-target');
      if (!el || typeof Gantt === 'undefined') return;
      el.innerHTML = '';
      const visible = this.ganttVisibleTasks;
      const dated = visible.filter(t => t.start_date || t.due_date);
      const critical = this.ganttShowCritical ? this.computeCriticalPathIds(dated) : new Set();
      const items = dated
        .map(t => {
          let start = t.start_date || t.due_date;
          let end = t.due_date || t.start_date;
          if (start === end) {
            const d = new Date(end);
            d.setDate(d.getDate() + 1);
            end = d.toISOString().slice(0, 10);
          }
          const visibleIds = new Set(visible.map(x => String(x.id)));
          const predIds = (t.predecessor_ids || [])
            .map(String)
            .filter(id => visibleIds.has(id));
          const typeCls = 'gantt-' + (t.type || 'Others').replace(/\s+/g, '-').toLowerCase();
          const critCls = critical.has(t.id) ? ' gantt-critical' : '';
          return {
            id: String(t.id),
            name: t.title,
            start,
            end,
            progress: t.progress || 0,
            dependencies: predIds.join(','),
            custom_class: typeCls + critCls
          };
        });
      if (items.length === 0) return;
      try {
        this.ganttInstance = new Gantt('#gantt-target', items, {
          view_mode: this.ganttViewMode || 'Week',
          bar_height: 22,
          padding: 14,
          on_click: (task) => {
            const t = this.tasks.find(x => String(x.id) === task.id);
            if (t) this.openDetail(t);
          },
          on_date_change: async (task, start, end) => {
            const id = parseInt(task.id);
            try {
              await this.api('/api/tasks/' + id, {
                method: 'PUT',
                body: {
                  start_date: start.toISOString().slice(0, 10),
                  due_date: end.toISOString().slice(0, 10)
                }
              });
              this.showToast('Tanggal diupdate');
              await this.loadTasks();
            } catch (e) {
              this.showToast(e.message);
            }
          }
        });
      } catch (e) {
        console.warn('Gantt render error', e);
      }
    }
};

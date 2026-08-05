/** Plan365 Deps mixin — loaded before app.js */
window.Plan365Deps = {
    // ---- Task Detail ----
    get depCandidateTasks() {
      if (!this.detailTask) return [];
      const used = new Set((this.detailDeps.predecessor_ids || []).map(Number));
      used.add(Number(this.detailTask.id));
      return this.tasks.filter(t => !used.has(Number(t.id)));
    },
    isTaskBlocked(task) {
      const preds = task.predecessor_ids || [];
      if (!preds.length) return false;
      const byId = Object.fromEntries(this.tasks.map(t => [t.id, t]));
      return preds.some(id => {
        const p = byId[id];
        return p && p.status !== 'Done' && p.status !== 'Handoff';
      });
    },
    async openDetail(task) {
      this.detailTask = task;
      this.depPickId = '';
      this.detailDeps = { predecessors: [], successors: [], blocked: false, predecessor_ids: [], successor_ids: [] };
      this.detailForm = {
        title: task.title,
        description: task.description || '',
        type: task.type,
        status: task.status,
        priority: task.priority,
        progress: task.progress || 0,
        start_date: task.start_date || '',
        due_date: task.due_date || '',
        assignee_id: task.assignee_id || null,
        figma_url: task.figma_url || '',
        pr_url: task.pr_url || ''
      };
      await this.loadDetailDeps();
    },
    async loadDetailDeps() {
      if (!this.detailTask) return;
      try {
        this.detailDeps = await this.api('/api/tasks/' + this.detailTask.id + '/dependencies');
      } catch (e) {
        this.detailDeps = { predecessors: [], successors: [], blocked: false, predecessor_ids: [], successor_ids: [] };
      }
    },
    async addDependency() {
      if (!this.detailTask || !this.depPickId) return;
      const pred = parseInt(this.depPickId);
      const lag = Math.max(0, parseInt(this.depLagDays) || 0);
      try {
        await this.api('/api/dependencies', {
          method: 'POST',
          body: {
            predecessor_id: pred,
            successor_id: this.detailTask.id,
            type: 'FS',
            lag_days: lag
          }
        });
        this.depPickId = '';
        this.depLagDays = 0;
        this.showToast(lag ? `Dependency + lag ${lag}d` : 'Dependency ditambahkan');
        await this.loadDetailDeps();
        await this.loadTasks();
        if (this.subView === 'gantt') this.$nextTick(() => this.renderGantt());
      } catch (e) {
        this.showToast(e.message || 'Gagal menambah dependency');
      }
    },
    async removeDependency(depId) {
      try {
        await this.api('/api/dependencies/' + depId, { method: 'DELETE' });
        this.showToast('Dependency dihapus');
        await this.loadDetailDeps();
        await this.loadTasks();
        if (this.subView === 'gantt') this.$nextTick(() => this.renderGantt());
      } catch (e) {
        this.showToast(e.message);
      }
    },
    async saveDetail() {
      if (!this.detailTask) return;
      try {
        if ((this.detailForm.status === 'Done' || this.detailForm.status === 'Handoff')
            && this.isTaskBlocked(this.detailTask)) {
          this.showToast('Blocked: selesaikan predecessor dulu');
          return;
        }
        const body = { ...this.detailForm };
        if (body.assignee_id === '' || body.assignee_id === 'null') body.assignee_id = null;
        else if (body.assignee_id) body.assignee_id = parseInt(body.assignee_id);
        const updated = await this.api('/api/tasks/' + this.detailTask.id, { method: 'PUT', body });
        const idx = this.tasks.findIndex(t => t.id === this.detailTask.id);
        if (idx >= 0) this.tasks[idx] = { ...this.tasks[idx], ...updated };
        this.detailTask = null;
        this.showToast('Task saved');
        if (this.subView === 'kanban') this.$nextTick(() => this.initKanban());
        if (this.subView === 'gantt') this.$nextTick(() => this.renderGantt());
      } catch(e) { this.showToast(e.message); }
    }
};

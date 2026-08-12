/** Plan365 Kanban mixin — loaded before app.js */
window.Plan365Kanban = {
    // ---- Kanban ----
    initKanban() {
      (this.kanbanSortables || []).forEach(s => { try { s.destroy(); } catch(e){} });
      this.kanbanSortables = [];
      if (typeof Sortable === 'undefined') return;
      document.querySelectorAll('.kanban-col').forEach(col => {
        const s = Sortable.create(col, {
          group: 'kanban',
          animation: 150,
          ghostClass: 'opacity-50',
          onAdd: async (evt) => {
            const id = parseInt(evt.item.dataset.id);
            const newStatus = evt.to.dataset.status;
            const t = this.tasks.find(x => x.id === id);
            if (t && (newStatus === 'Done' || newStatus === 'Handoff') && this.isTaskBlocked(t)) {
              this.showToast('Blocked: selesaikan predecessor dulu');
              await this.loadTasks();
              this.$nextTick(() => this.initKanban());
              return;
            }
            try {
              await this.api('/api/tasks/' + id + '/status?status=' + encodeURIComponent(newStatus), { method: 'PATCH' });
              if (t) t.status = newStatus;
              this.showToast('Status → ' + newStatus);
            } catch(e) {
              this.showToast(e.message);
              await this.loadTasks();
              this.$nextTick(() => this.initKanban());
            }
          }
        });
        this.kanbanSortables.push(s);
      });
    }
};

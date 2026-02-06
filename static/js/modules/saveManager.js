// ==========================================
// 存档管理模块 - 保存/加载/退出确认
// ==========================================

export class SaveManager {
    constructor(wsManager) {
        this.wsManager = wsManager;
        this.isExiting = false;
    }

    /**
     * 显示退出确认弹窗
     */
    showExitConfirmModal() {
        if (this.isExiting) return;

        // 移除旧弹窗（如果存在）
        const oldModal = document.getElementById('exit-confirm-modal');
        if (oldModal) oldModal.remove();

        // 创建弹窗
        const modal = document.createElement('div');
        modal.id = 'exit-confirm-modal';
        modal.innerHTML = `
            <div class="modal fade show" style="display:block;background:rgba(0,0,0,0.7);z-index:10000;" tabindex="-1">
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content border-0 shadow-lg">
                        <div class="modal-header bg-warning text-dark">
                            <h5 class="modal-title">
                                <i class="bi bi-exclamation-triangle-fill me-2"></i>
                                确认退出游戏
                            </h5>
                        </div>
                        <div class="modal-body p-4">
                            <div class="alert alert-info mb-3">
                                <strong>💾 是否保存当前游戏进度？</strong>
                            </div>
                            <div class="text-muted small">
                                <p class="mb-2">
                                    <strong>保存并退出：</strong>将当前游戏进度保存到数据库，下次登录时继续游戏
                                </p>
                                <p class="mb-0">
                                    <strong>不保存退出：</strong>放弃当前进度，下次登录将开始新游戏
                                </p>
                            </div>
                        </div>
                        <div class="modal-footer d-flex justify-content-between">
                            <button type="button" class="btn btn-secondary" id="btn-cancel-exit">
                                <i class="bi bi-x-circle me-1"></i>取消
                            </button>
                            <div>
                                <button type="button" class="btn btn-danger me-2" id="btn-exit-no-save">
                                    <i class="bi bi-trash me-1"></i>不保存退出
                                </button>
                                <button type="button" class="btn btn-success" id="btn-save-and-exit">
                                    <i class="bi bi-save me-1"></i>保存并退出
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // 绑定事件
        document.getElementById('btn-cancel-exit').onclick = () => {
            this.closeModal();
        };

        document.getElementById('btn-exit-no-save').onclick = () => {
            this.exitWithoutSave();
        };

        document.getElementById('btn-save-and-exit').onclick = () => {
            this.saveAndExit();
        };
    }

    /**
     * 关闭弹窗
     */
    closeModal() {
        const modal = document.getElementById('exit-confirm-modal');
        if (modal) modal.remove();
    }

    /**
     * 保存并退出
     */
    saveAndExit() {
        if (this.isExiting) return;
        this.isExiting = true;

        this.showSavingIndicator();
        this.wsManager.send({ action: 'save_and_exit' });

        // 设置超时保护
        setTimeout(() => {
            if (this.isExiting) {
                console.warn('[SaveManager] Save timeout, forcing redirect');
                window.location.href = '/';
            }
        }, 10000); // 10秒超时
    }

    /**
     * 不保存退出
     */
    exitWithoutSave() {
        if (this.isExiting) return;

        if (!confirm('确定不保存进度直接退出吗？当前进度将会丢失！')) {
            return;
        }

        this.isExiting = true;
        this.showSavingIndicator('正在退出...');
        this.wsManager.send({ action: 'exit_without_save' });

        // 1秒后强制跳转
        setTimeout(() => {
            window.location.href = '/';
        }, 1000);
    }

    /**
     * 手动保存（不退出）
     */
    saveGame() {
        console.log('[SaveManager] Manual save requested');
        this.wsManager.send({ action: 'save_game' });

        // 显示保存提示
        this.showToast('正在保存游戏...', 'info');
    }

    /**
     * 处理保存结果
     */
    handleSaveResult(success, message) {
        console.log(`[SaveManager] Save result: ${success ? 'success' : 'failed'} - ${message}`);

        if (this.isExiting && success) {
            this.showToast('保存成功，正在返回首页...', 'success');
            setTimeout(() => {
                window.location.href = '/';
            }, 1500);
        } else if (this.isExiting && !success) {
            this.showToast('保存失败，但仍将退出游戏', 'warning');
            setTimeout(() => {
                window.location.href = '/';
            }, 2000);
        } else {
            // 手动保存
            this.showToast(message, success ? 'success' : 'danger');
        }
    }

    /**
     * 处理退出确认
     */
    handleExitConfirmed() {
        this.showToast('正在返回首页...', 'info');
        setTimeout(() => {
            window.location.href = '/';
        }, 1000);
    }

    /**
     * 显示保存中指示器
     */
    showSavingIndicator(text = '正在保存游戏...') {
        this.closeModal();

        const indicator = document.createElement('div');
        indicator.id = 'saving-indicator';
        indicator.innerHTML = `
            <div style="position:fixed;top:0;left:0;right:0;bottom:0;
                        background:rgba(0,0,0,0.8);z-index:10001;
                        display:flex;align-items:center;justify-content:center;">
                <div class="text-center text-white">
                    <div class="spinner-border mb-3" role="status" style="width:3rem;height:3rem;">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <h4>${text}</h4>
                </div>
            </div>
        `;
        document.body.appendChild(indicator);
    }

    /**
     * 显示 Toast 提示
     */
    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `alert alert-${type} position-fixed top-0 start-50 translate-middle-x mt-3`;
        toast.style.zIndex = '10002';
        toast.innerHTML = `
            <strong>${message}</strong>
        `;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.remove();
        }, 3000);
    }
}

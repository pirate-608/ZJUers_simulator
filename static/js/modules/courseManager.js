// ==========================================
// 课程管理模块 - 课程列表渲染与交互
// ==========================================

import { CONFIG } from './config.js';
import { gameState } from './gameState.js';

export class CourseManager {
    constructor(wsManager) {
        this.wsManager = wsManager;
    }

    renderCourseList(masteryData, statesData) {
        const listContainer = document.getElementById('course-list');
        if (!listContainer) return 0;

        console.log('[CourseManager] renderCourseList called:', {
            masteryData,
            statesData,
            metadata: gameState.getCourseMetadata()
        });

        listContainer.innerHTML = '';

        let total = 0, count = 0;
        const safeStates = statesData || {};
        const courseMetadata = gameState.getCourseMetadata();

        courseMetadata.forEach(course => {
            const cId = String(course.id);
            const val = parseFloat(masteryData[cId] || 0);
            console.log(`[CourseManager] Rendering ${course.name}: id=${cId}, val=${val}`);
            total += val;
            count++;

            let currentState = safeStates[cId];
            if (currentState === undefined || currentState === null) {
                currentState = 1;
            }
            currentState = parseInt(currentState);

            let badgeClass = "bg-secondary";
            if (val > 60) badgeClass = "bg-warning";
            if (val > 85) badgeClass = "bg-success";

            const item = document.createElement('div');
            item.className = "list-group-item p-2 mb-2 border-0 shadow-sm course-item flat-course-item";
            item.style.transition = "all 0.3s";

            if (currentState === 2) item.style.borderLeft = "5px solid #dc3545";
            else if (currentState === 0) item.style.borderLeft = "5px solid #6c757d";
            else item.style.borderLeft = "5px solid #0d6efd";

            if (item.dataset.lastState && item.dataset.lastState != currentState) {
                item.classList.add('state-changed');
                setTimeout(() => item.classList.remove('state-changed'), 600);
            }
            item.dataset.lastState = currentState;

            const stateConfig = CONFIG.COEFFS[currentState] || CONFIG.COEFFS[1];

            item.innerHTML = `
                <div class="d-flex w-100 justify-content-between align-items-center mb-1">
                    <h6 class="mb-0 fw-bold text-dark" style="font-size:1rem;">
                        ${course.name} 
                        <small class="text-muted ms-1" style="font-weight:normal;">(${course.credits}学分)</small>
                    </h6>
                    <span class="badge ${badgeClass} rounded-pill" style="font-size:0.9em;">${val.toFixed(1)}%</span>
                </div>
                <div class="progress mb-2" style="height: 6px; background-color: #e9ecef;">
                    <div class="progress-bar ${badgeClass}" role="progressbar" style="width: ${val}%"></div>
                </div>
                <div class="d-flex justify-content-between align-items-center mt-2">
                    <div class="d-flex align-items-center">
                        <small class="text-muted me-2">策略:</small>
                        <div class="btn-group btn-group-sm" role="group">
                            ${this.renderStateButton(cId, 0, currentState)}
                            ${this.renderStateButton(cId, 1, currentState)}
                            ${this.renderStateButton(cId, 2, currentState)}
                        </div>
                    </div>
                    <span class="fs-5" title="当前状态">${stateConfig.emoji}</span>
                </div>
            `;
            listContainer.appendChild(item);
        });

        const avgProgress = count > 0 ? (total / count) : 0;
        return avgProgress;
    }

    renderStateButton(courseId, stateValue, currentState) {
        const config = CONFIG.COEFFS[stateValue];
        const isActive = (stateValue === currentState);
        const btnClass = isActive ? config.activeClass : config.class;
        const activeStyle = isActive ? "box-shadow: 0 0 0 2px rgba(0,0,0,0.1) inset;" : "";

        return `<button type="button" class="btn ${btnClass} ${isActive ? 'active fw-bold' : ''}" 
                style="${activeStyle} min-width: 40px;"
                onclick="window.changeCourseState('${courseId}', ${stateValue})">
                ${config.name}
                </button>`;
    }

    changeCourseState(courseId, newState) {
        gameState.setCourseState(courseId, newState);

        const stats = gameState.getStats();
        const courses = stats.courses || {};
        const states = gameState.getCourseStates();

        this.renderCourseList(courses, states);
        this.updateEnergyProjection();

        this.wsManager.send({
            action: "change_course_state",
            target: courseId,
            value: newState
        });
    }

    updateEnergyProjection() {
        const courseMetadata = gameState.getCourseMetadata();
        if (courseMetadata.length === 0) return;

        let totalCredits = 0;
        let totalDrainWeight = 0;
        const currentCourseStates = gameState.getCourseStates();

        courseMetadata.forEach(c => {
            const credits = parseFloat(c.credits);
            totalCredits += credits;
            const state = currentCourseStates[c.id] || 1;
            const drainCoeff = CONFIG.COEFFS[state].drain;
            totalDrainWeight += credits * drainCoeff;
        });

        if (totalCredits === 0) totalCredits = 1;
        const weightedFactor = totalDrainWeight / totalCredits;
        const estimatedCost = Math.floor(CONFIG.BASE_DRAIN * weightedFactor);

        let label = document.getElementById('energy-prediction');
        if (!label) {
            const energyContainer = document.getElementById('val-energy');
            if (energyContainer && energyContainer.parentNode) {
                label = document.createElement('small');
                label.id = 'energy-prediction';
                label.className = "ms-2 fw-bold";
                energyContainer.parentNode.appendChild(label);
            }
        }

        if (label) {
            if (estimatedCost === 0) {
                label.className = "ms-2 fw-bold text-success";
                label.innerText = "(+2/tick 回复)";
            } else {
                label.className = estimatedCost > 5 ? "ms-2 fw-bold text-danger" : "ms-2 fw-bold text-muted";
                label.innerText = `(-${estimatedCost}/tick)`;
            }
        }
    }
}

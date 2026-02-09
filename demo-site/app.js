// Demo App JavaScript

// Simulate login
function handleLogin(event) {
    event.preventDefault();

    // Support both normal mode (by ID) and break mode (by data-testid/class)
    const email = (document.getElementById('email') || document.querySelector('[data-testid="email-input"]'))?.value;
    const password = (document.getElementById('password') || document.querySelector('[data-testid="password-input"]'))?.value;
    const loginBtn = document.getElementById('login-btn') || document.querySelector('[data-testid="signin-btn"]') || document.querySelector('.signin-button');

    // Show loading state
    loginBtn.innerHTML = `
        <svg class="spinner" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10" stroke-opacity="0.25"/>
            <path d="M12 2a10 10 0 0 1 10 10" stroke-linecap="round">
                <animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="1s" repeatCount="indefinite"/>
            </path>
        </svg>
        Signing in...
    `;
    loginBtn.disabled = true;

    // Simulate API call
    setTimeout(() => {
        // Hide login, show dashboard
        document.getElementById('login-page').classList.add('hidden');
        document.getElementById('dashboard-page').classList.remove('hidden');

        // Reset button
        loginBtn.innerHTML = 'Sign in';
        loginBtn.disabled = false;

        showToast('Welcome back, John!');
    }, 1500);
}

// Show signup (just a demo redirect back to login)
function showSignup() {
    showToast('Signup coming soon!');
}

// Open modal
document.getElementById('new-project-btn')?.addEventListener('click', () => {
    document.getElementById('modal-overlay').classList.remove('hidden');
});

// Close modal
document.getElementById('close-modal')?.addEventListener('click', closeModal);
document.getElementById('modal-overlay')?.addEventListener('click', (e) => {
    if (e.target === document.getElementById('modal-overlay')) {
        closeModal();
    }
});

function closeModal() {
    document.getElementById('modal-overlay').classList.add('hidden');
    document.getElementById('project-form').reset();
}

// Create project
function handleCreateProject(event) {
    event.preventDefault();

    const projectName = document.getElementById('project-name').value;
    const createBtn = document.getElementById('create-project-btn');

    // Show loading
    createBtn.innerHTML = 'Creating...';
    createBtn.disabled = true;

    setTimeout(() => {
        // Add new project to list
        const projectsList = document.getElementById('projects-list');
        const colors = ['#6366f1', '#10b981', '#f59e0b', '#ec4899', '#06b6d4'];
        const randomColor = colors[Math.floor(Math.random() * colors.length)];

        const newProject = document.createElement('div');
        newProject.className = 'project-item';
        newProject.setAttribute('data-testid', `project-${Date.now()}`);
        newProject.innerHTML = `
            <div class="project-color" style="background: ${randomColor}"></div>
            <div class="project-info">
                <h3>${projectName}</h3>
                <p>0 tasks</p>
            </div>
            <div class="project-progress">
                <div class="progress-bar">
                    <div class="progress-fill" style="width: 0%"></div>
                </div>
                <span>0%</span>
            </div>
        `;

        projectsList.insertBefore(newProject, projectsList.firstChild);

        // Close modal and reset
        closeModal();
        createBtn.innerHTML = 'Create Project';
        createBtn.disabled = false;

        showToast(`Project "${projectName}" created!`);
    }, 1000);
}

// Toast notification
function showToast(message) {
    const toast = document.getElementById('toast');
    const toastMessage = document.getElementById('toast-message');

    toastMessage.textContent = message;
    toast.classList.remove('hidden');

    setTimeout(() => {
        toast.classList.add('hidden');
    }, 3000);
}

// Nav link handling
document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', (e) => {
        e.preventDefault();
        document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
        e.target.classList.add('active');
        showToast(`Navigated to ${e.target.textContent}`);
    });
});

// Project click handling
document.querySelectorAll('.project-item').forEach(item => {
    item.addEventListener('click', () => {
        const projectName = item.querySelector('h3').textContent;
        showToast(`Opened "${projectName}"`);
    });
});

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Escape to close modal
    if (e.key === 'Escape') {
        closeModal();
    }

    // Ctrl/Cmd + K for quick action (demo)
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        showToast('Quick search coming soon!');
    }
});

// ============================================
// BREAKING CHANGES MODE - For Self-Healing Demo
// ============================================
// Add ?break=true to URL to simulate selector changes

const urlParams = new URLSearchParams(window.location.search);
const breakMode = urlParams.get('break') === 'true';

if (breakMode) {
    console.log('🔧 Break mode enabled - selectors will be changed');

    // Change login button ID
    const loginBtn = document.getElementById('login-btn');
    if (loginBtn) {
        loginBtn.removeAttribute('id');
        loginBtn.classList.add('signin-button'); // Changed class
        loginBtn.setAttribute('data-testid', 'signin-btn'); // Changed testid
    }

    // Change email input
    const emailInput = document.getElementById('email');
    if (emailInput) {
        emailInput.removeAttribute('id');
        emailInput.setAttribute('name', 'user-email'); // Changed name
        emailInput.classList.add('email-field');
    }

    // Change password input
    const passwordInput = document.getElementById('password');
    if (passwordInput) {
        passwordInput.removeAttribute('id');
        passwordInput.setAttribute('name', 'user-password');
        passwordInput.classList.add('password-field');
    }

    // Change new project button
    const newProjectBtn = document.getElementById('new-project-btn');
    if (newProjectBtn) {
        newProjectBtn.removeAttribute('id');
        newProjectBtn.classList.add('add-project-btn');
        newProjectBtn.setAttribute('data-testid', 'add-project');
    }

    // Change project name input
    const projectNameInput = document.getElementById('project-name');
    if (projectNameInput) {
        projectNameInput.removeAttribute('id');
        projectNameInput.setAttribute('name', 'name');
        projectNameInput.classList.add('project-title-input');
    }

    // Change create project button
    const createProjectBtn = document.getElementById('create-project-btn');
    if (createProjectBtn) {
        createProjectBtn.removeAttribute('id');
        createProjectBtn.classList.add('submit-project');
        createProjectBtn.setAttribute('data-testid', 'submit-project-btn');
    }

    // Add visual indicator
    const indicator = document.createElement('div');
    indicator.style.cssText = `
        position: fixed;
        top: 16px;
        left: 50%;
        transform: translateX(-50%);
        background: #f59e0b;
        color: #000;
        padding: 8px 16px;
        border-radius: 8px;
        font-size: 12px;
        font-weight: 600;
        z-index: 9999;
    `;
    indicator.textContent = '⚠️ BREAK MODE - Selectors Changed';
    document.body.appendChild(indicator);
}

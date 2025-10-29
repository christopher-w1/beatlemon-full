let isLoginMode = true;
const parent_url = window.location.href.split('/').slice(0, -1).join('/');
const index_url = `${parent_url}/index.html`;


// ---------------- UI Functions ----------------

// Toggle between Login and Sign Up modes
function toggleAuthMode() {
    isLoginMode = !isLoginMode;
    const confirmPasswordField  = document.getElementById('auth_confirm_pass');
    const usernameField         = document.getElementById('auth_username');
    const toggleButton          = document.getElementById('toggle-btn');
    const secretKeyField        = document.getElementById('auth_registration_key');
    if (isLoginMode) {
        confirmPasswordField.style.display = 'none';
        usernameField.style.display = 'none';
        secretKeyField.style.display = 'none';
        toggleButton.textContent = 'Switch to Sign Up';
    } else {
        confirmPasswordField.style.display = 'block';
        usernameField.style.display = 'block';
        secretKeyField.style.display = 'block';
        toggleButton.textContent = 'Switch to Login';
    }
}

// Handle form submission
function submitAuthForm() {
    if (isLoginMode) {
        handleLogin();
    } else {
        handleSignUp();
    }
}


// ---------------- LOGIN ----------------

async function handleLogin() {
    const email = document.getElementById('auth_email').value.trim();
    const password = document.getElementById('auth_pass').value;
    if (!email || !password) {
        show_error("Email and Password are required!");
        return;
    }

    try {
        const result = await apiLoginUser({ email, password });
        console.log("Logged in:", result.username);
        localStorage.setItem("session_key", result.session_key);
        localStorage.setItem("session_id", result.session_id);
        localStorage.setItem("username", result.username);
        localStorage.setItem("email", result.email);
        show_error("");
        window.location.href = index_url;
    } catch (err) {
        show_error(err.message);
    }
}

// ---------------- SIGN-UP ----------------

async function handleSignUp() {
    const email = document.getElementById('auth_email').value.trim();
    const password = document.getElementById('auth_pass').value;
    const confirmPassword = document.getElementById('auth_confirm_pass').value;
    const username = document.getElementById('auth_username').value.trim();
    const registration_key = document.getElementById('auth_registration_key').value.trim();

    if (password !== confirmPassword) {
        show_error("Passwords do not match!");
        return;
    }
    if (!username) {
        show_error("Username is required for sign up!");
        return;
    }
    if (password.length < 7) {
        show_error("Password must be at least 7 characters long!");
        return;
    }
    if (!email.includes('@')) {
        show_error("Invalid email address!");
        return;
    }

    try {
        const result = await apiRegisterUser({
            registration_key,
            email,
            username,
            password,
            lastfm_user: null
        });

        console.log("Registered and logged in:", result.username);
        localStorage.setItem("session_key", result.session_key);
        localStorage.setItem("session_id", result.session_id);
        localStorage.setItem("username", result.username);
        localStorage.setItem("email", result.email);
        show_error("");
        window.location.href = index_url;
    } catch (err) {
        show_error(err.message);
    }
}

// ---------------- ERROR HANDLING ----------------

function show_error(msg) {
    const errorDiv = document.getElementById('login-error-message');
    errorDiv.textContent = msg;
    errorDiv.style.display = msg ? 'block' : 'none';
}

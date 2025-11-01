const parent_url = window.location.href.split('/').slice(0, -1).join('/');

async function checkAuth() {
    // Check if user is authenticated by locating session_key in localStorage
    let authorized = await apiCheckAuth();
    if (!authorized) {
        // If not authenticated, redirect to login page
        console.warn('User not authenticated, redirecting to login page');
        window.location.href = `${parent_url}/login.html`;
        return false;
    } else {
        console.log('User is authenticated');
        // Proceed with loading the main application
        return true;
    }
}
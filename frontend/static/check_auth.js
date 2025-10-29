const parent_url = window.location.href.split('/').slice(0, -1).join('/');

// Check if user is authenticated by locating session_key in localStorage
if (!localStorage.getItem('session_key')) {
    // If not authenticated, redirect to login page
    console.log('User not authenticated, redirecting to login page');
    window.location.href = `${parent_url}/login.html`;
} else {
    console.log('User is authenticated');
    // Proceed with loading the main application
}
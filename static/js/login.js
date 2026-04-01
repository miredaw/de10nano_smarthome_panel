document.addEventListener('DOMContentLoaded', function() {
    const loginForm = document.getElementById('loginForm');
    const errorMessage = document.getElementById('errorMessage');
    const loginBtn = document.getElementById('loginBtn');
    const loginText = document.getElementById('loginText');
    const loginSpinner = document.getElementById('loginSpinner');

    loginForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;
        
        // Clear previous errors
        errorMessage.classList.remove('show');
        errorMessage.textContent = '';
        
        // Disable button and show spinner
        loginBtn.disabled = true;
        loginText.style.display = 'none';
        loginSpinner.style.display = 'block';
        
        try {
            const response = await fetch('/api/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ username, password })
            });
            
            const data = await response.json();
            
            if (response.ok && data.success) {
                // Redirect to dashboard
                window.location.href = data.redirect || '/';
            } else {
                // Show error message
                errorMessage.textContent = data.error || 'Login failed';
                errorMessage.classList.add('show');
                
                // Re-enable button
                loginBtn.disabled = false;
                loginText.style.display = 'block';
                loginSpinner.style.display = 'none';
            }
        } catch (error) {
            console.error('Login error:', error);
            errorMessage.textContent = 'An error occurred. Please try again.';
            errorMessage.classList.add('show');
            
            // Re-enable button
            loginBtn.disabled = false;
            loginText.style.display = 'block';
            loginSpinner.style.display = 'none';
        }
    });
    
    // Clear error on input
    document.getElementById('username').addEventListener('input', function() {
        errorMessage.classList.remove('show');
    });
    
    document.getElementById('password').addEventListener('input', function() {
        errorMessage.classList.remove('show');
    });
});

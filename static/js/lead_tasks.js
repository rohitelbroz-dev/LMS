// Task checkbox toggle functionality for lead detail page

document.addEventListener('DOMContentLoaded', function() {
    // Get all task checkboxes
    const taskCheckboxes = document.querySelectorAll('.task-checkbox');
    
    taskCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function(e) {
            const activityId = this.dataset.activityId;
            const leadId = this.dataset.leadId;
            const taskItem = this.closest('.task-item');
            const isChecked = this.checked;
            
            // Store original state for error rollback
            const originalState = !isChecked;
            
            // Optimistic UI update
            toggleTaskVisualState(taskItem, isChecked);
            
            // Send AJAX request to toggle completion
            fetch(`/lead/${leadId}/activity/${activityId}/toggle_complete`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Success - show toast notification
                    showToast(data.message, 'success');
                    
                    // Update the badge if needed
                    updateTaskBadge(taskItem, data.is_completed);
                    
                    console.log(`Task ${activityId} ${data.is_completed ? 'completed' : 'reopened'}`);
                } else {
                    // Error - rollback UI changes
                    checkbox.checked = originalState;
                    toggleTaskVisualState(taskItem, originalState);
                    showToast(data.message || 'Failed to update task', 'error');
                }
            })
            .catch(error => {
                console.error('Error toggling task:', error);
                // Rollback UI changes on error
                checkbox.checked = originalState;
                toggleTaskVisualState(taskItem, originalState);
                showToast('An error occurred while updating the task', 'error');
            });
        });
    });
});

// Toggle visual state of task item
function toggleTaskVisualState(taskItem, isCompleted) {
    if (isCompleted) {
        taskItem.classList.add('task-completed');
    } else {
        taskItem.classList.remove('task-completed');
    }
}

// Update task badge (Done/Not Done)
function updateTaskBadge(taskItem, isCompleted) {
    const taskTitle = taskItem.querySelector('.task-title');
    const existingDoneBadge = taskTitle.querySelector('.task-done-badge');
    
    if (isCompleted) {
        // Add "Done" badge if it doesn't exist
        if (!existingDoneBadge) {
            const badge = document.createElement('span');
            badge.className = 'badge bg-success ms-2 task-done-badge';
            badge.innerHTML = '<i class="fas fa-check"></i> Done';
            taskTitle.appendChild(badge);
        }
    } else {
        // Remove only the "Done" badge (preserves other badges like due dates)
        if (existingDoneBadge) {
            existingDoneBadge.remove();
        }
    }
}

// Show toast notification
function showToast(message, type = 'info') {
    // Check if toast container exists
    let toastContainer = document.getElementById('toast-container');
    
    if (!toastContainer) {
        // Create toast container if it doesn't exist
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 9999;';
        document.body.appendChild(toastContainer);
    }
    
    // Create toast element
    const toast = document.createElement('div');
    toast.className = `alert alert-${type === 'success' ? 'success' : 'danger'} alert-dismissible fade show task-toast`;
    toast.style.cssText = 'min-width: 250px; animation: slideIn 0.3s ease;';
    toast.setAttribute('role', 'alert');
    
    toast.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    toastContainer.appendChild(toast);
    
    // Auto-remove after 3 seconds
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 3000);
}

// Socket.IO event listener for real-time updates from other users
if (typeof socket !== 'undefined') {
    socket.on('lead_updated', function(data) {
        if (data.update_type === 'activity_completed' || data.update_type === 'activity_reopened') {
            const activityId = data.activity_id;
            const checkbox = document.querySelector(`.task-checkbox[data-activity-id="${activityId}"]`);
            
            if (checkbox) {
                const taskItem = checkbox.closest('.task-item');
                const isCompleted = data.is_completed;
                
                // Update UI based on Socket.IO event
                checkbox.checked = isCompleted;
                toggleTaskVisualState(taskItem, isCompleted);
                updateTaskBadge(taskItem, isCompleted);
                
                // Show notification that someone else updated the task
                if (data.updated_by && typeof currentUserName !== 'undefined' && data.updated_by !== currentUserName) {
                    showToast(`${data.updated_by} ${isCompleted ? 'completed' : 'reopened'} this task`, 'info');
                }
            }
        }
    });
}

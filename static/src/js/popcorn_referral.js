// Simple referral functionality - just copy the referral link when button is clicked
$(document).ready(function() {
    // Handle referral button click
    $(document).on('click', '.popcorn-referral-btn', function(e) {
        e.preventDefault();
        e.stopPropagation();
        
        var $button = $(this);
        var eventId = $button.data('event-id');
        var referralPrize = parseFloat($button.data('referral-prize'));
        var currencySymbol = $button.data('currency-symbol');
        
        if (!eventId) {
            alert('Error: Missing event information. Please refresh the page and try again.');
            return;
        }
        
        // Generate referral link
        var formData = new FormData();
        formData.append('event_id', eventId);
        
        fetch('/popcorn/referral/generate', {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
            }
        })
        .then(function(response) {
            return response.json();
        })
        .then(function(data) {
            if (data.success) {
                // Copy the referral link to clipboard
                var referralLink = data.referral_link;
                
                // Create a temporary input element to copy the link
                var tempInput = document.createElement('input');
                tempInput.value = referralLink;
                document.body.appendChild(tempInput);
                tempInput.select();
                tempInput.setSelectionRange(0, 99999); // For mobile devices
                
                try {
                    document.execCommand('copy');
                    document.body.removeChild(tempInput);
                    
                    // Show success message
                    var originalText = $button.html();
                    $button.html('<i class="fa fa-check"></i> <span t-translation="on">Copied!</span>');
                    $button.addClass('popcorn-btn-success');
                    
                    setTimeout(function() {
                        $button.html(originalText);
                        $button.removeClass('popcorn-btn-success');
                    }, 2000);
                    
                } catch (err) {
                    document.body.removeChild(tempInput);
                    alert('Referral link generated: ' + referralLink + '\n\nPlease copy this link manually.');
                }
            } else {
                alert('Failed to generate referral link. Please try again.');
            }
        })
        .catch(function(error) {
            alert('Failed to generate referral link. Please try again.');
        });
    });
});

document.addEventListener('DOMContentLoaded', () => {
  // Initialize any tooltips or popovers
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
  });

  // Blood Group Filtering
  const filterSelect = document.getElementById('bloodGroupFilter');
  if (filterSelect) {
    filterSelect.addEventListener('change', function () {
      const selected = this.value;
      const cards = document.querySelectorAll('.request-card-wrapper');
      cards.forEach(card => {
        if (selected === 'all' || card.getAttribute('data-blood-group') === selected) {
          card.style.display = 'block';
        } else {
          card.style.display = 'none';
        }
      });
    });
  }
});


document.addEventListener("DOMContentLoaded", () => {
    const countElement = document.querySelector('.glow-ball span');
  
    function animateCount(target, element) {
      let current = 0;
      const interval = setInterval(() => {
        element.textContent = current;
        if (current >= target) {
          clearInterval(interval);
        } else {
          current++;
        }
      }, 50);
    }
  
    fetch("status.json")
      .then(response => response.json())
      .then(data => {
        const appliedCount = data.applied_count || 0;
        const rejectedCount = data.rejected_count || 0;
        const totalCount = appliedCount + rejectedCount;

            animateCount(totalCount, countElement);
       })
      .catch(error => {
        console.error("❌ Failed to load status.json:", error);
        countElement.textContent = "0";
      });
  });
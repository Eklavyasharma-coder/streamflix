document.addEventListener("DOMContentLoaded", () => {
  const player = document.querySelector("#player");
  if (!player) return;
  const movieId = player.dataset.movie;
  let lastSent = 0;
  player.addEventListener("loadedmetadata", () => {
    const saved = Number(player.dataset.position || 0);
    if (saved > 0 && saved < player.duration) player.currentTime = saved;
  });
  player.addEventListener("timeupdate", async () => {
    if (Math.floor(player.currentTime) - lastSent < 10) return;
    lastSent = Math.floor(player.currentTime);
    try { await fetch(`/api/history/${movieId}`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({position:lastSent})}); } catch (_) {}
  });
  window.addEventListener("pagehide", () => {
    const body = JSON.stringify({position:Math.floor(player.currentTime || 0)});
    navigator.sendBeacon(`/api/history/${movieId}`, new Blob([body], {type:"application/json"}));
  });
});
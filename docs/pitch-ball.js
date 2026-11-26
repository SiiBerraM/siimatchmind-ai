(function(){
  function cleanName(raw){
    if(!raw) return "";
    let s = String(raw).replace(/\s+/g, " ").trim();
    // إزالة تكرار الكلمات المتجاورة مثل "نيوكاسل ني يونايتد" أو تكرار الكلمة نفسها
    s = s.replace(/\b(\S+)\s+\1\b/gi, "$1");
    // تنظيف أقواس مقطوعة مثل "و(" أو "ب("
    s = s.replace(/[\(\[][^\)\]]{1,2}$/g, "").trim();
    return s;
  }

  function fixNames(){
    document.querySelectorAll("b, .name, .team-name, [data-team-name]").forEach(function(el){
      if(el.children.length === 0 && el.textContent){
        const fixed = cleanName(el.textContent);
        if(fixed && fixed !== el.textContent.trim()){
          el.textContent = fixed;
        }
      }
    });
  }

  function mountPitch(){
    const host = document.getElementById("app") || document.querySelector("main") || document.body;
    if(!host || document.getElementById("smmPitchWrap")) return;

    const wrap = document.createElement("div");
    wrap.id = "smmPitchWrap";
    wrap.className = "smm-pitch-wrap";
    wrap.innerHTML = '<div class="smm-pitch" id="smmPitch"><div class="smm-goal-l"></div><div class="smm-goal-r"></div><div class="smm-ball" id="smmBall"></div></div>';
    host.insertBefore(wrap, host.firstChild);

    const pitch = document.getElementById("smmPitch");
    const ball = document.getElementById("smmBall");
    let w = pitch.clientWidth || 320;
    let h = pitch.clientHeight || 92;
    let x = w * 0.5, y = h * 0.5;
    let vx = 1.6, vy = 0.7;
    let dragging = false;

    function syncSize(){
      w = pitch.clientWidth || 320;
      h = pitch.clientHeight || 92;
      x = Math.min(Math.max(12, x), w - 12);
      y = Math.min(Math.max(12, y), h - 12);
    }
    window.addEventListener("resize", syncSize);

    function kickFrom(clientX, clientY){
      const r = pitch.getBoundingClientRect();
      const tx = Math.min(Math.max(10, clientX - r.left), r.width - 10);
      const ty = Math.min(Math.max(10, clientY - r.top), r.height - 10);
      const dx = tx - x;
      const dy = ty - y;
      x = tx; y = ty;
      vx = (dx || (Math.random() > 0.5 ? 2 : -2)) * 0.35;
      vy = (dy || (Math.random() > 0.5 ? 1.2 : -1.2)) * 0.35;
      const speed = Math.hypot(vx, vy);
      if(speed < 1.8){
        const ang = Math.atan2(vy || 0.4, vx || 1.5);
        vx = Math.cos(ang) * 2.2;
        vy = Math.sin(ang) * 2.2;
      }
    }

    pitch.addEventListener("pointerdown", function(e){
      dragging = true;
      kickFrom(e.clientX, e.clientY);
    });
    window.addEventListener("pointermove", function(e){
      if(!dragging) return;
      kickFrom(e.clientX, e.clientY);
    });
    window.addEventListener("pointerup", function(){
      dragging = false;
    });

    function step(){
      if(!dragging){
        x += vx;
        y += vy;
        if(x <= 10){ x = 10; vx = Math.abs(vx); }
        if(x >= w - 10){ x = w - 10; vx = -Math.abs(vx); }
        if(y <= 10){ y = 10; vy = Math.abs(vy); }
        if(y >= h - 10){ y = h - 10; vy = -Math.abs(vy); }
        // حركة انسيابية مستمرة بين المرميين
        if(Math.abs(vx) < 1.1) vx = vx >= 0 ? 1.4 : -1.4;
      }
      ball.style.left = x + "px";
      ball.style.top = y + "px";
      requestAnimationFrame(step);
    }
    step();
  }

  function run(){
    mountPitch();
    fixNames();
  }

  document.addEventListener("DOMContentLoaded", run);
  window.addEventListener("hashchange", function(){ setTimeout(run, 80); });
  const obs = new MutationObserver(function(){ fixNames(); });
  obs.observe(document.documentElement, { childList:true, subtree:true });
})();

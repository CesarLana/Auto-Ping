// Auto Ping-Pong Easter Egg - PRO VERSION

let pongClickCount = 0;
let pongClickTimer = null;

// Audio Context for Beeps
const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
function playBeep(freq, type, duration, vol) {
    if(audioCtx.state === 'suspended') audioCtx.resume();
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
    gain.gain.setValueAtTime(vol, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + duration);
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.start();
    osc.stop(audioCtx.currentTime + duration);
}

function playHitSound() { playBeep(600, 'square', 0.1, 0.1); }
function playWallSound() { playBeep(400, 'sine', 0.1, 0.1); }
function playScoreSound() { playBeep(200, 'sawtooth', 0.5, 0.2); }

function initPongListener() {
    const titleEl = document.querySelector('.sidebar-title');
    if(titleEl) {
        titleEl.style.cursor = 'pointer';
        titleEl.title = 'Segredo?';
        titleEl.addEventListener('click', () => {
            pongClickCount++;
            clearTimeout(pongClickTimer);
            pongClickTimer = setTimeout(() => { pongClickCount = 0; }, 2000);
            
            if(pongClickCount >= 5) {
                pongClickCount = 0;
                startPongGame();
            }
        });
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPongListener);
} else {
    initPongListener();
}

function startPongGame() {
    if(document.getElementById('pong-overlay')) return;

    const overlay = document.createElement('div');
    overlay.id = 'pong-overlay';
    overlay.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(10,12,16,0.98);z-index:9999;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#00F0FF;font-family:var(--font-family-base, monospace); backdrop-filter: blur(10px); animation: fadeIn 0.5s ease-out;';
    
    overlay.innerHTML = `
        <h1 style="margin-bottom:20px;text-shadow:0 0 15px #00F0FF, 0 0 30px #00F0FF;font-size:3rem;letter-spacing:4px;text-transform:uppercase;font-weight:900;">Cyber Ping</h1>
        <div style="position:relative;">
            <canvas id="pong-canvas" width="800" height="450" style="border:1px solid rgba(0,240,255,0.3);box-shadow:0 0 40px rgba(0,240,255,0.2), inset 0 0 20px rgba(0,240,255,0.1);border-radius:12px;background:radial-gradient(circle at center, #111 0%, #000 100%);"></canvas>
            <div id="pong-score" style="position:absolute;top:30px;width:100%;text-align:center;font-size:64px;font-weight:900;opacity:0.2;pointer-events:none;letter-spacing:20px;">0 - 0</div>
            <div id="pong-speed" style="position:absolute;bottom:10px;right:15px;font-size:12px;color:#FFD500;opacity:0.5;font-family:monospace;">VELOCIDADE: 1.0x</div>
        </div>
        <div style="margin-top:30px;font-size:16px;color:#8B949E;display:flex;align-items:center;gap:24px;">
            <span style="background:rgba(255,255,255,0.05);padding:8px 16px;border-radius:8px;">W/S ou Setas = Mover</span>
            <button onclick="closePong()" style="background:transparent;border:2px solid #FF3366;color:#FF3366;padding:8px 24px;border-radius:8px;cursor:pointer;font-weight:bold;text-transform:uppercase;transition:all 0.2s;box-shadow:0 0 10px rgba(255,51,102,0.2);" onmouseover="this.style.background='#FF3366';this.style.color='#fff';" onmouseout="this.style.background='transparent';this.style.color='#FF3366';">Sair do Jogo</button>
        </div>
    `;
    document.body.appendChild(overlay);

    initPong();
}

let pongLoop;

function closePong() {
    const overlay = document.getElementById('pong-overlay');
    if(overlay) overlay.remove();
    cancelAnimationFrame(pongLoop);
}

function initPong() {
    const canvas = document.getElementById('pong-canvas');
    const ctx = canvas.getContext('2d');
    
    const paddleWidth = 12, paddleHeight = 80;
    const ballSize = 12;
    const baseSpeed = 6;
    
    let player = { x: 40, y: canvas.height/2 - paddleHeight/2, score: 0 };
    let ai = { x: canvas.width - 52, y: canvas.height/2 - paddleHeight/2, score: 0, targetY: 0 };
    let ball = { x: canvas.width/2, y: canvas.height/2, dx: baseSpeed, dy: baseSpeed, speedMultiplier: 1.0 };
    
    let particles = [];
    let trails = [];
    
    let upPressed = false, downPressed = false;
    
    const keydownHandler = (e) => {
        if(['w', 'ArrowUp', 'W'].includes(e.key)) { upPressed = true; e.preventDefault(); }
        if(['s', 'ArrowDown', 'S'].includes(e.key)) { downPressed = true; e.preventDefault(); }
    };
    const keyupHandler = (e) => {
        if(['w', 'ArrowUp', 'W'].includes(e.key)) upPressed = false;
        if(['s', 'ArrowDown', 'S'].includes(e.key)) downPressed = false;
    };
    
    window.addEventListener('keydown', keydownHandler, {passive: false});
    window.addEventListener('keyup', keyupHandler);

    const oldClose = closePong;
    window.closePong = () => {
        window.removeEventListener('keydown', keydownHandler);
        window.removeEventListener('keyup', keyupHandler);
        oldClose();
    };
    
    function resetBall(scorer) {
        ball.x = canvas.width/2;
        ball.y = canvas.height/2;
        ball.speedMultiplier = 1.0;
        ball.dx = (scorer === 'player' ? -baseSpeed : baseSpeed);
        ball.dy = (Math.random() > 0.5 ? baseSpeed : -baseSpeed) * (Math.random() * 0.4 + 0.8);
        document.getElementById('pong-speed').innerText = `VELOCIDADE: ${ball.speedMultiplier.toFixed(1)}x`;
        trails = [];
    }
    
    function createParticles(x, y, color) {
        for(let i=0; i<15; i++) {
            particles.push({
                x: x, y: y,
                vx: (Math.random() - 0.5) * 10,
                vy: (Math.random() - 0.5) * 10,
                life: 1.0,
                color: color
            });
        }
    }
    
    function update() {
        // Player move
        if(upPressed && player.y > 0) player.y -= 8;
        if(downPressed && player.y < canvas.height - paddleHeight) player.y += 8;
        
        // AI Logic (Predictive with delay)
        let aiSpeed = 5 + (ball.speedMultiplier * 2);
        if(Math.random() > 0.1) { // 10% chance to not react immediately
            if(ball.dx > 0) {
                // Ball moving towards AI
                ai.targetY = ball.y - paddleHeight/2;
            } else {
                // Ball moving away, go to center
                ai.targetY = canvas.height/2 - paddleHeight/2;
            }
        }
        
        // Move AI towards target smoothly
        if(ai.y < ai.targetY - 10) ai.y += aiSpeed;
        else if(ai.y > ai.targetY + 10) ai.y -= aiSpeed;
        
        if(ai.y < 0) ai.y = 0;
        if(ai.y > canvas.height - paddleHeight) ai.y = canvas.height - paddleHeight;

        // Ball Trail
        trails.push({x: ball.x, y: ball.y, alpha: 0.5});
        if(trails.length > 10) trails.shift();

        // Ball move
        ball.x += ball.dx * ball.speedMultiplier;
        ball.y += ball.dy * ball.speedMultiplier;
        
        // Wall collision
        if(ball.y <= 0 || ball.y + ballSize >= canvas.height) {
            ball.dy *= -1;
            playWallSound();
        }
        
        // Paddle collision (Player)
        if(ball.dx < 0 && ball.x <= player.x + paddleWidth && ball.x + ballSize >= player.x && ball.y + ballSize >= player.y && ball.y <= player.y + paddleHeight) {
            let hitPoint = (ball.y + ballSize/2) - (player.y + paddleHeight/2);
            ball.dy = hitPoint * 0.2; // Angle based on where it hit
            ball.dx *= -1;
            ball.speedMultiplier = Math.min(2.5, ball.speedMultiplier + 0.1);
            ball.x = player.x + paddleWidth;
            playHitSound();
            createParticles(ball.x, ball.y, '#00F0FF');
            document.getElementById('pong-speed').innerText = `VELOCIDADE: ${ball.speedMultiplier.toFixed(1)}x`;
        }
        
        // Paddle collision (AI)
        if(ball.dx > 0 && ball.x + ballSize >= ai.x && ball.x <= ai.x + paddleWidth && ball.y + ballSize >= ai.y && ball.y <= ai.y + paddleHeight) {
            let hitPoint = (ball.y + ballSize/2) - (ai.y + paddleHeight/2);
            ball.dy = hitPoint * 0.2;
            ball.dx *= -1;
            ball.speedMultiplier = Math.min(2.5, ball.speedMultiplier + 0.1);
            ball.x = ai.x - ballSize;
            playHitSound();
            createParticles(ball.x, ball.y, '#FF3366');
            document.getElementById('pong-speed').innerText = `VELOCIDADE: ${ball.speedMultiplier.toFixed(1)}x`;
        }
        
        // Scoring
        if(ball.x < -50) {
            ai.score++;
            updateScore();
            playScoreSound();
            resetBall('ai');
        } else if(ball.x > canvas.width + 50) {
            player.score++;
            updateScore();
            playScoreSound();
            resetBall('player');
        }
        
        // Update Particles
        for(let i = particles.length - 1; i >= 0; i--) {
            let p = particles[i];
            p.x += p.vx;
            p.y += p.vy;
            p.life -= 0.05;
            if(p.life <= 0) particles.splice(i, 1);
        }
    }
    
    function updateScore() {
        document.getElementById('pong-score').innerText = `${player.score} - ${ai.score}`;
    }
    
    function draw() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // Draw Net
        ctx.fillStyle = 'rgba(0, 240, 255, 0.15)';
        for(let i=15; i<canvas.height; i+=40) {
            ctx.fillRect(canvas.width/2 - 2, i, 4, 20);
        }
        
        // Draw Trails
        trails.forEach((t, index) => {
            ctx.fillStyle = `rgba(0, 240, 255, ${t.alpha * (index/trails.length)})`;
            ctx.beginPath();
            ctx.arc(t.x + ballSize/2, t.y + ballSize/2, (ballSize/2) * (index/trails.length), 0, Math.PI*2);
            ctx.fill();
        });
        
        // Draw Player
        ctx.fillStyle = '#00F0FF';
        ctx.shadowColor = '#00F0FF';
        ctx.shadowBlur = 15;
        ctx.fillRect(player.x, player.y, paddleWidth, paddleHeight);
        
        // Draw AI
        ctx.fillStyle = '#FF3366';
        ctx.shadowColor = '#FF3366';
        ctx.shadowBlur = 15;
        ctx.fillRect(ai.x, ai.y, paddleWidth, paddleHeight);
        
        // Draw Ball
        ctx.fillStyle = '#FFFFFF';
        ctx.shadowColor = '#00E5FF';
        ctx.shadowBlur = 20;
        ctx.beginPath();
        ctx.arc(ball.x + ballSize/2, ball.y + ballSize/2, ballSize/2, 0, Math.PI*2);
        ctx.fill();
        ctx.shadowBlur = 0;
        
        // Draw Particles
        particles.forEach(p => {
            ctx.fillStyle = p.color;
            ctx.globalAlpha = p.life;
            ctx.beginPath();
            ctx.arc(p.x, p.y, 3, 0, Math.PI*2);
            ctx.fill();
        });
        ctx.globalAlpha = 1.0; // Reset
    }
    
    function loop() {
        update();
        draw();
        pongLoop = requestAnimationFrame(loop);
    }
    
    // Resume audio context if browser requires user interaction first
    const initAudio = () => {
        if(audioCtx.state === 'suspended') audioCtx.resume();
        window.removeEventListener('click', initAudio);
        window.removeEventListener('keydown', initAudio);
    };
    window.addEventListener('click', initAudio);
    window.addEventListener('keydown', initAudio);
    
    loop();
}

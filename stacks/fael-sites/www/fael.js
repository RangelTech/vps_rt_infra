/* Colab Fael: troca a foto do topo pela cena temática do Fael e põe a faixa "Colab Fael - Adriano Camargo" no fim. */
(() => {
  const IG = 'https://www.instagram.com/faelgomeess/', ARROBA = '@faelgomeess'
  const sub = location.hostname.split('.')[0]
  const img = `/__fael/img/${sub}.webp`
  document.documentElement.style.setProperty('--fael-img', `url("${img}")`)
  document.title = 'Colab Fael · ' + document.title
  const ac = (() => {
    const escura = (c) => { const m = (c || '').match(/\d+(\.\d+)?/g); if (!m) return true; const [r, g, b, a = 1] = m.map(Number); return a < .5 || (r + g + b) < 150 || (r > 235 && g > 235 && b > 235) }
    for (const [sel, prop] of [['h1 em', 'color'], ['h1 span', 'color'], ['.btn-pri, .btn.pri, .btn-primario', 'backgroundColor'], ['h1 strong', 'color'], ['.selo', 'color']]) {
      const e = document.querySelector(sel); const c = e && getComputedStyle(e)[prop]; if (c && !escura(c)) return c }
    return '#e2c27e' })()
  document.documentElement.style.setProperty('--fael-ac', ac)

  // topo
  const fundo = document.querySelector('.cine-fundo, .cine-heroi .kb, .heroi-azul .fundo, .heroi .fundo')
  let heroi
  if (fundo) { fundo.classList.add('fael-alvo'); fundo.removeAttribute('aria-label'); heroi = fundo.parentElement }
  else {
    heroi = document.querySelector('main section, body > section, .heroi, .hero')
    if (heroi) { const bg = document.createElement('div'); bg.className = 'fael-bg fael-alvo'; heroi.prepend(bg) }
  }
  if (heroi) {
    heroi.classList.add('fael-heroi')
    const h1 = heroi.querySelector('h1')
    if (h1) { const s = document.createElement('span'); s.className = 'fael-selo'; s.innerHTML = `<img src="/__fael/avatar.jpg" alt="">Colab Fael`; h1.parentElement.insertBefore(s, h1.previousElementSibling && /selo|chip|sobre/.test(h1.previousElementSibling.className) ? h1.previousElementSibling : h1) }
  }

  // vidro líquido: topo com texto centralizado ganha um painel de vidro atrás do texto
  const h1c = heroi && heroi.querySelector('h1')
  if (h1c && getComputedStyle(h1c).textAlign === 'center') {
    const pai = h1c.parentElement, vidro = document.createElement('div')
    vidro.className = 'fael-vidro'
    let ini = h1c; while (ini.previousElementSibling && /fael-selo|selo|chip/.test(ini.previousElementSibling.className)) ini = ini.previousElementSibling
    pai.insertBefore(vidro, ini)
    let e = vidro.nextElementSibling
    while (e && !/janela|mock|tela|video|img|grade/.test(e.className) && ['H1', 'P', 'DIV', 'SPAN'].includes(e.tagName) && !(e.tagName === 'DIV' && e.querySelector('img,video,canvas') && !e.querySelector('a.btn'))) {
      const prox = e.nextElementSibling; vidro.appendChild(e); e = prox }
  }

  // fim
  const sec = document.createElement('section')
  sec.className = 'fael-colab'
  sec.innerHTML = `<div class="c"><img class="av" src="/__fael/avatar.jpg" alt="Fael">
    <div><small>Parceria</small><h2>Colab Fael - Adriano Camargo</h2>
    <p>Uma parceria do Fael com o Adriano Camargo. Acompanhe o Fael no Instagram.</p>
    <a class="ig" href="${IG}" target="_blank" rel="noopener"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1" fill="currentColor"/></svg>${ARROBA}</a></div></div>`
  const pe = document.querySelector('footer')
  pe ? pe.parentElement.insertBefore(sec, pe) : document.body.appendChild(sec)
})()

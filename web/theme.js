/* Loaded before styles to apply the chosen appearance without a bright flash. */
(() => {
  'use strict';
  const key='arcade-theme', choices=['system','light','dark'];
  const system=window.matchMedia('(prefers-color-scheme: dark)');
  let choice='system';
  try {const stored=window.localStorage.getItem(key);if(choices.includes(stored))choice=stored;} catch {}
  function apply(){
    const theme=choice==='system'?(system.matches?'dark':'light'):choice;
    document.documentElement.dataset.theme=theme;
    document.documentElement.style.colorScheme=theme;
    const control=document.querySelector('[data-theme-choice]');
    if(control)control.value=choice;
  }
  apply();
  system.addEventListener('change',apply);
  window.addEventListener('storage',event=>{
    if(event.key!==key)return;
    choice=choices.includes(event.newValue)?event.newValue:'system';apply();
  });
  function mount(){
    const control=document.querySelector('[data-theme-choice]');
    if(!control)return;
    control.value=choice;
    control.addEventListener('change',()=>{
      if(!choices.includes(control.value))return;
      choice=control.value;
      try{window.localStorage.setItem(key,choice);}catch{}
      apply();
    });
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();
})();

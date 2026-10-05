const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
function load(saved,dark=false){
  const values=new Map([['arcade-theme',saved],['arcade-progress','keep-me']]);
  const listeners={},control={value:'',addEventListener(type,fn){listeners[type]=fn;}};
  const media={matches:dark,addEventListener(type,fn){this.changed=fn;}};
  const document={documentElement:{dataset:{},style:{}},readyState:'complete',querySelector:()=>control};
  const window={localStorage:{getItem:key=>values.get(key),setItem:(k,v)=>values.set(k,v)},matchMedia:()=>media,addEventListener(type,fn){listeners[type]=fn;}};
  vm.runInNewContext(fs.readFileSync(require.resolve('../theme.js'),'utf8'),{window,document});
  return {values,listeners,control,media,document};
}
test('saved dark theme wins over system and preserves study progress',()=>{
  const x=load('dark');assert.equal(x.document.documentElement.dataset.theme,'dark');assert.equal(x.values.get('arcade-progress'),'keep-me');
  x.control.value='light';x.listeners.change();assert.equal(x.values.get('arcade-theme'),'light');assert.equal(x.document.documentElement.dataset.theme,'light');
});
test('system theme follows preference changes; explicit choice does not',()=>{
  const x=load(null,true);assert.equal(x.control.value,'system');assert.equal(x.document.documentElement.dataset.theme,'dark');
  x.media.matches=false;x.media.changed();assert.equal(x.document.documentElement.dataset.theme,'light');
  x.control.value='dark';x.listeners.change();x.media.changed();assert.equal(x.document.documentElement.dataset.theme,'dark');
});
test('another tab updates the theme control',()=>{
  const x=load('light');x.listeners.storage({key:'arcade-theme',newValue:'dark'});assert.equal(x.control.value,'dark');assert.equal(x.document.documentElement.dataset.theme,'dark');
});

/* Explicit search only: no keystroke requests to the public Photon instance. */
(function (global) {
  class AddressSearch {
    constructor({form, input, button, results, status, search, onPick}) {
      Object.assign(this, {form,input,button,results,status,search,onPick});
      this.generation=0;
      form.addEventListener('submit', event => { event.preventDefault(); this.run(); });
      input.addEventListener('input', () => this.clear());
    }

    clear() {
      this.generation++;
      if (this.controller) this.controller.abort();
      this.results.replaceChildren();
      this.status.textContent='';
      this.button.disabled=false;
    }

    async run() {
      this.clear();
      const generation=this.generation;
      const query=this.input.value.trim();
      if (query.length<3 || query.length>200) {
        this.status.textContent='Введите от 3 до 200 символов.';
        return;
      }
      this.controller=new AbortController();
      this.button.disabled=true;
      this.status.textContent='Ищем адрес…';
      try {
        const items=await this.search(query,this.controller.signal);
        if (generation!==this.generation) return;
        if (!items.length) this.status.textContent='Ничего не найдено. Уточните адрес или выберите точку на карте.';
        else this.status.textContent='Выберите результат и проверьте точку на карте.';
        for (const item of items) {
          const li=document.createElement('li');
          const button=document.createElement('button');
          button.type='button';
          button.className='text-left w-full p-2 border rounded hover:bg-slate-100';
          button.textContent=item.label;
          button.addEventListener('click',()=>{
            this.onPick(item);
            this.results.replaceChildren();
            this.status.textContent=`Выбрано: ${item.label}`;
          });
          li.appendChild(button);
          this.results.appendChild(li);
        }
      } catch (error) {
        if (generation===this.generation && error.name!=='AbortError') {
          this.status.textContent=error.message || 'Поиск недоступен. Выберите точку на карте.';
        }
      } finally {
        if (generation===this.generation) this.button.disabled=false;
      }
    }
  }
  global.AddressSearch=AddressSearch;
})(window);

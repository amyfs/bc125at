function rowState(idx){
    let ro_row = document.getElementById(`row-${idx}`)
    let rw_row = document.getElementById(`row-${idx}-edit`)
    if (ro_row.classList.contains('hidden')){
        ro_row.classList.remove('hidden') 
        rw_row.classList.add('hidden')
    }else{
        ro_row.classList.add('hidden')
        rw_row.classList.remove('hidden')
    }
}

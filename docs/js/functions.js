function openSection(newSection) {
    $('.section').css('display', 'none');
    $('.section').css('overflow', 'hidden');
    $('#' + newSection).css('display', 'block');
    $('#' + newSection).css('overflow', 'visible');
}
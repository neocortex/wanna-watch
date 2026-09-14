/* Keep password errors accessible without reflecting input into the page. */
if (new URLSearchParams(location.search).has('failed')) {
  document.querySelector('#login-error').hidden = false;
  document.querySelector('#password').focus();
}

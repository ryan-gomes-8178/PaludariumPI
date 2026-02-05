<script>
  import { Modal, ModalCloseButton } from '@keenmate/svelte-adminlte';
  import { onMount } from 'svelte';
  import { successNotification, errorNotification } from '../providers/notification-provider';

  import { _ } from 'svelte-i18n';
  import { createForm } from 'felte';

  import Field from '../components/form/Field.svelte';
  import PasswordField from '../components/form/PasswordField.svelte';
  import Helper from '../components/form/Helper.svelte';
  import { doLogin, doLogin2fa } from '../stores/authentication';

  let wrapper_show;
  let wrapper_hide;
  let validated = false;
  let login_error = false;
  let requires_2fa = false;
  let preauth_token = null;
  let username_cache = null;

  let editForm;

  const _processForm = async (values, context) => {
    validated = true;
    login_error = false;
    if (context.form.checkValidity()) {
      if (!requires_2fa) {
        let login = await doLogin(values.username, values.password);
        if (login && login.success) {
          if (login.requires_2fa) {
            requires_2fa = true;
            preauth_token = login.preauth_token;
            username_cache = values.username;
            validated = false;
            setTimeout(() => {
              const tokenInput = document.querySelector('form input[name="totp_code"]');
              if (tokenInput) {
                tokenInput.focus();
              }
            }, 50);
            return;
          }

          successNotification(
            $_('notification.login.message.ok', { default: 'You are successfully logged in.' }),
            $_('notification.login.title', { default: 'Login' }),
          );
          hide();
        } else {
          errorNotification(
            $_('notification.login.message.error', { derfault: 'Sorry, but login is invalid' }),
            $_('notification.login.title', { default: 'Login' }),
          );
          login_error = true;
        }
      } else {
        let result = await doLogin2fa(username_cache, values.totp_code, preauth_token);
        if (result && result.success) {
          successNotification(
            $_('notification.login.message.ok', { default: 'You are successfully logged in.' }),
            $_('notification.login.title', { default: 'Login' }),
          );
          hide();
        } else {
          errorNotification(
            result?.error || $_('notification.login.message.error', { derfault: 'Sorry, but login is invalid' }),
            $_('notification.login.title', { default: 'Login' }),
          );
          login_error = true;
        }
      }
      validated = false;
    }
  };

  const { form, isSubmitting, createSubmitHandler, reset } = createForm({
    onSubmit: _processForm,
  });

  const formSubmit = createSubmitHandler({
    onSubmit: _processForm,
  });

  export const show = () => {
    reset();
    validated = false;
    login_error = false;
    requires_2fa = false;
    preauth_token = null;
    username_cache = null;
    wrapper_show();

    setTimeout(() => {
      const input = document.querySelector('form input[name="username"]');
      if (input) {
        input.focus();
      }
    }, 650);
  };

  export const hide = () => {
    wrapper_hide();
  };

  onMount(() => {
    editForm.setAttribute('novalidate', 'novalidate');
  });
</script>

<Modal center bind:show="{wrapper_show}" bind:hide="{wrapper_hide}">
  <svelte:fragment slot="header">
    <i class="fas fa-key mr-2"></i>
    {$_('modal.login.title', { default: 'Login' })}
    <Helper />
  </svelte:fragment>
  <form
    id="loginForm"
    class="form-horizontal needs-validation"
    class:was-validated="{validated}"
    use:form
    bind:this="{editForm}"
  >
    <h3 class="text-danger text-center mb-3" class:d-none="{!login_error}">
      {$_('modal.login.error', { default: 'Invalid login' })}
    </h3>
    <Field
      type="text"
      name="username"
      class="col-8"
      required="{true}"
      disabled="{requires_2fa}"
      horizontal="{true}"
      label="{$_('modal.login.form.username.label', { default: 'Username' })}"
      help="{$_('modal.login.form.username.help', { default: 'Enter the username' })}"
      invalid="{$_('modal.login.form.username.invalid', { default: 'Username cannot be empty' })}"
    />
    <PasswordField
      name="password"
      class="col-8"
      required="{true}"
      disabled="{requires_2fa}"
      horizontal="{true}"
      label="{$_('modal.login.form.password.label', { default: 'Password' })}"
      help="{$_('modal.login.form.password.help', { default: 'Enter the password' })}"
      invalid="{$_('modal.login.form.password.invalid', { default: 'Password cannot be empty' })}"
    />
    {#if requires_2fa}
      <Field
        type="text"
        name="totp_code"
        class="col-8"
        required="{true}"
        horizontal="{true}"
        label="{$_('modal.login.form.totp.label', { default: '2FA code' })}"
        help="{$_('modal.login.form.totp.help', { default: 'Enter the 6-digit code from your authenticator app.' })}"
        invalid="{$_('modal.login.form.totp.invalid', { default: '2FA code is required.' })}"
      />
    {/if}
    <!-- We need this nasty hack to make submit with enter key to work -->
    <button type="submit" style="display:none"> </button>
  </form>
  <svelte:fragment slot="actions">
    <div class="d-flex justify-content-between w-100">
      <ModalCloseButton>
        {$_('modal.general.close', { default: 'Close' })}
      </ModalCloseButton>
      <button type="button" class="btn btn-primary" disabled="{$isSubmitting}" on:click="{formSubmit}">
        <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true" class:d-none="{!$isSubmitting}"
        ></span>
        {$_('modal.login.form.submit', { default: 'Login' })}
      </button>
    </div>
  </svelte:fragment>
</Modal>

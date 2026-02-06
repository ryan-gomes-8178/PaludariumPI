<script>
  import { onMount, onDestroy } from 'svelte';
  import { PageHeader } from '@keenmate/svelte-adminlte';
  import { _ } from 'svelte-i18n';

  import { setCustomPageTitle, customPageTitleUsed } from '../stores/page-title';
  import { getCustomConfig } from '../config';

  import Card from '../user-controls/Card.svelte';

  let settings = getCustomConfig();

  onMount(() => {
    setCustomPageTitle($_('about.title', { default: 'About' }));
  });

  onDestroy(() => {
    customPageTitleUsed.set(false);
  });
</script>

<PageHeader>
  {$_('about.title', { default: 'About' })}
</PageHeader>
<div class="container-fluid">
  <div class="row">
    <div class="col">
      <Card loading="{false}" noPadding="{false}">
        <svelte:fragment slot="header">
          <i class="fas fa-info mr-2"></i>PaludariumPI v {settings.version}
        </svelte:fragment>
        <img
          src="/img/terrariumpi.jpg"
          class="img-thumbnail float-right"
          alt="PaludariumPI Logo version {settings.version}"
        />
        <p>
          PaludariumPI started in 2024 to keep my crested gecko Marty and his aquatic friends happy. It’s adapted from
          <a href="https://github.com/theyosh/TerrariumPI" target="_blank" rel="noopener noreferrer">TerrariumPI</a>
          by TheYOSH and built to automate a paludarium enclosure where aquatic and terrestrial life thrive together.
          It currently runs my setup for Marty, vampire crabs, rummynose tetras, ram cichlids, harlequin rasboras,
          bristlenose plecos, nerite snails, amano shrimp, assassin snails, apistogramma, and julii corydoras.
          It’s a home-automation brain for all of them, and it works just as well for indoor plants, vivariums, and more.
        </p>
        <p>
          This software is written in Python3 and uses the <a
            href="https://adminlte.io/"
            target="_blank"
            rel="noopener noreferrer">AdminLTE admin web interface</a
          >. To make the GUI reactive we use
          <a href="https://svelte.dev" target="_blank" rel="noopener noreferrer">Svelte</a>.
        </p>
        <p>
          For documentation about how to install and set it up, see <a
            href="https://github.com/ryan-gomes-8178/PaludariumPI"
            target="_blank"
            rel="noopener noreferrer">https://github.com/ryan-gomes-8178/PaludariumPI</a
          >.
        </p>
        <p>
          For bugs and feature requests please open a <a
            href="https://github.com/ryan-gomes-8178/PaludariumPI/issues"
            target="_blank"
            rel="noopener noreferrer">GitHub issue</a
          >. <img alt="GitHub issues" src="https://img.shields.io/github/issues-raw/ryan-gomes-8178/PaludariumPI" /> /
          <img
            alt="GitHub closed issues"
            src="https://img.shields.io/github/issues-closed-raw/ryan-gomes-8178/PaludariumPI?color=00ff"
          />
        </p>
        <p>
          PaludariumPI is proudly built on top of TerrariumPI’s foundation—huge thanks to TheYOSH and the community for
          the original project.
        </p>
        <p>
          If you’re running a PaludariumPI setup, feel free to share photos or stories in the project repo.
        </p>
        <p>
          API Documentation:
          <a href="api/redoc/" target="_blank">ReDoc</a> /
          <a href="api/swagger/" target="_blank">Swagger</a>
        </p>
        <p>
          <br />&copy; Copyright
          <a
            href="https://theyosh.github.io/TerrariumPI/posts/2014/08/28/early-terrariumpi-version/"
            target="_blank"
            rel="noopener noreferrer">2014</a
          >
          - 2026<br /><a href="https://github.com/ryan-gomes-8178" target="_blank" rel="noopener noreferrer">Ryan Gomes</a>
        </p>
      </Card>
    </div>
  </div>
</div>

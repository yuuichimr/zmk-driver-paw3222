# ZMK PAW3222 Driver

This driver enables the use of the PIXART PAW3222 optical sensor with the ZMK framework.

## Overview

The PAW3222 is a low-power optical mouse sensor suitable for tracking applications such as mice and trackballs. This driver communicates with the PAW3222 sensor via SPI interface.

## Installation

1. Add as a ZMK module in your west.yml:

```
manifest:
  remotes:
    - name: zmkfirmware
      url-base: https://github.com/zmkfirmware
    - name: sekigon-gonnoc
      url-base: https://github.com/sekigon-gonnoc
  projects:
    - name: zmk
      remote: zmkfirmware
      revision: main
      import: app/west.yml
    - name: zmk-driver-paw3222
      remote: sekigon-gonnoc
      revision: main
```

## Device Tree Configuration

Configure in your shield or board config file (.overlay or .dtsi):

```dts
&pinctrl {
    spi0_default: spi0_default {
        group1 {
            psels = <NRF_PSEL(SPIM_SCK, 0, 12)>,
                <NRF_PSEL(SPIM_MOSI, 1, 9)>,
                <NRF_PSEL(SPIM_MISO, 1, 9)>;
        };
    };

    spi0_sleep: spi0_sleep {
        group1 {
            psels = <NRF_PSEL(SPIM_SCK, 0, 12)>,
                <NRF_PSEL(SPIM_MOSI, 1, 9)>,
                <NRF_PSEL(SPIM_MISO, 1, 9)>;
            low-power-enable;
        };
    };
};

&spi0 {
    status = "okay";
    compatible = "nordic,nrf-spim";
    pinctrl-0 = <&spi0_default>;
    pinctrl-1 = <&spi0_sleep>;
    pinctrl-names = "default", "sleep";
    cs-gpios = <&gpio0 13 GPIO_ACTIVE_LOW>;

    trackball: trackball@0 {
        status = "okay";
        compatible = "pixart,paw3222";
        reg = <0>;
        spi-max-frequency = <2000000>;
        irq-gpios = <&gpio0 15 GPIO_ACTIVE_LOW>;
    };
};
```

## Enable the module in your keyboard's Kconfig file

Add the following to your keyboard's `Kconfig.defconfig`:

```kconfig
if ZMK_KEYBOARD_YOUR_KEYBOARD

config ZMK_POINTING
    default y

config PAW3222
    default y

endif
```

## Properties

- `irq-gpios`: GPIO connected to the motion pin (required)
- `power-gpios`: GPIO that switches the sensor supply (optional)
- `res-cpi`: CPI resolution for the sensor (optional)
- `force-awake`: Initialize the sensor in "force awake" mode (optional, boolean)

## Kconfig

- `CONFIG_PAW3222_POLL_INTERVAL_MS` (default `15`, range 4-50): polling interval used
  while the sensor keeps reporting motion. Lower = smoother cursor, slightly more current.

## Notes

- Works with `CONFIG_PM_DEVICE_RUNTIME=y`: the driver takes a runtime-PM reference
  at init, so the sensor is no longer left suspended (previously it never reported
  motion when runtime PM was enabled).

## Example keyboard

[`keyboard/`](keyboard/) contains **Tsumugi**, an open low-profile wireless split
keyboard with a PAW3222 trackball built on this driver (PCB, case, ZMK firmware).

---

# ZMK PAW3222 ドライバ

このドライバは、PIXART PAW3222光学センサーをZMKフレームワークで使用できるようにします。

## 概要

PAW3222は、マウスやトラックボールなどのトラッキングアプリケーションに適した低消費電力の光学マウスセンサーです。このドライバはSPIインターフェースを介してPAW3222センサーと通信します。

## インストール

1. ZMKモジュールとして追加：

```
# west.yml に追加
manifest:
  remotes:
    - name: zmkfirmware
      url-base: https://github.com/zmkfirmware
    - name: sekigon-gonnoc
      url-base: https://github.com/sekigon-gonnoc
  projects:
    - name: zmk
      remote: zmkfirmware
      revision: main
      import: app/west.yml
    - name: zmk-driver-paw3222
      remote: sekigon-gonnoc
      revision: main
```

## デバイスツリー設定

シールドまたはボード設定ファイル（.overlayまたは.dtsi）で設定：

```dts
&pinctrl {
    spi0_default: spi0_default {
        group1 {
            psels = <NRF_PSEL(SPIM_SCK, 0, 12)>,
                <NRF_PSEL(SPIM_MOSI, 1, 9)>,
                <NRF_PSEL(SPIM_MISO, 1, 9)>;
        };
    };

    spi0_sleep: spi0_sleep {
        group1 {
            psels = <NRF_PSEL(SPIM_SCK, 0, 12)>,
                <NRF_PSEL(SPIM_MOSI, 1, 9)>,
                <NRF_PSEL(SPIM_MISO, 1, 9)>;
            low-power-enable;
        };
    };
};

&spi0 {
    status = "okay";
    compatible = "nordic,nrf-spim";
    pinctrl-0 = <&spi0_default>;
    pinctrl-1 = <&spi0_sleep>;
    pinctrl-names = "default", "sleep";
    cs-gpios = <&gpio0 13 GPIO_ACTIVE_LOW>;

    trackball: trackball@0 {
        status = "okay";
        compatible = "pixart,paw3222";
        reg = <0>;
        spi-max-frequency = <2000000>;
        irq-gpios = <&gpio0 15 GPIO_ACTIVE_LOW>;
    };
};
```

## キーボードのKconfigファイルでモジュールを有効化

キーボードの `Kconfig.defconfig` に以下を追加：

```kconfig
if ZMK_KEYBOARD_YOUR_KEYBOARD

config ZMK_POINTING
    default y

config PAW3222
    default y

endif
```

## プロパティ

- `irq-gpios`: モーションピンに接続されたGPIO（必須）
- `power-gpios`: センサー電源を切り替えるGPIO（任意）
- `res-cpi`: センサーのCPI解像度（任意）
- `force-awake`: センサーを「強制起動」モードで初期化（任意、ブール値）

## Kconfig

- `CONFIG_PAW3222_POLL_INTERVAL_MS`（既定 `15`、4〜50）: 動き検出中のポーリング間隔。
  小さいほどカーソルが滑らかになり、消費電流はわずかに増えます。

## 補足

- `CONFIG_PM_DEVICE_RUNTIME=y` でも動作します。初期化時にランタイムPMの参照を取得するため、
  以前のように「ランタイムPM有効時にセンサーがサスペンドされたまま動かない」問題は起きません。

## 作例キーボード

[`keyboard/`](keyboard/) に、このドライバを使ったロープロファイル無線分割トラックボールキーボード
**Tsumugi（紡）** の設計一式（PCB・ケース・ZMKファームウェア）があります。

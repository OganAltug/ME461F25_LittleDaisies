// Wokwi Custom Chip - L293D
// corrected l293d.chip.c

#include "wokwi-api.h"
#include <stdio.h>
#include <stdlib.h>

typedef struct {
  pin_t pin_en1, pin_in1, pin_out1, pin_in2, pin_out2;
  pin_t pin_en2, pin_in3, pin_out3, pin_in4, pin_out4;
} chip_state_t;

void update_motor(pin_t en, pin_t in1, pin_t out1, pin_t in2, pin_t out2) {
  // Read the Enable pin. If High, pass signals through.
  if (pin_read(en)) {
    pin_write(out1, pin_read(in1));
    pin_write(out2, pin_read(in2));
  } else {
    // If disabled, turn outputs off (High Impedance)
    pin_mode(out1, INPUT); 
    pin_mode(out2, INPUT);
  }
}

void chip_pin_change(void *user_data, pin_t pin, uint32_t value) {
  chip_state_t *chip = (chip_state_t*)user_data;
  update_motor(chip->pin_en1, chip->pin_in1, chip->pin_out1, chip->pin_in2, chip->pin_out2);
  update_motor(chip->pin_en2, chip->pin_in3, chip->pin_out3, chip->pin_in4, chip->pin_out4);
}

void chip_init() {
  chip_state_t *chip = malloc(sizeof(chip_state_t));

  // --- Assign Logical Pins to Variables ---
  chip->pin_en1 = pin_init("EN1", INPUT);
  chip->pin_in1 = pin_init("IN1", INPUT);
  chip->pin_out1 = pin_init("OUT1", OUTPUT);
  chip->pin_in2 = pin_init("IN2", INPUT);
  chip->pin_out2 = pin_init("OUT2", OUTPUT);

  chip->pin_en2 = pin_init("EN2", INPUT);
  chip->pin_in3 = pin_init("IN3", INPUT);
  chip->pin_out3 = pin_init("OUT3", OUTPUT);
  chip->pin_in4 = pin_init("IN4", INPUT);
  chip->pin_out4 = pin_init("OUT4", OUTPUT);

  // --- ERROR WAS HERE ---
  // Do NOT assign these to chip->pin_in4. Just initialize them.
  pin_init("VCC1", INPUT); 
  pin_init("VCC2", INPUT);
  pin_init("GND", INPUT);

  const pin_watch_config_t watch_config = {
    .edge = BOTH,
    .pin_change = chip_pin_change,
    .user_data = chip,
  };

  // Watch for changes
  pin_watch(chip->pin_en1, &watch_config);
  pin_watch(chip->pin_in1, &watch_config);
  pin_watch(chip->pin_in2, &watch_config);
  
  pin_watch(chip->pin_en2, &watch_config);
  pin_watch(chip->pin_in3, &watch_config);
  pin_watch(chip->pin_in4, &watch_config);
}